package lightinstall

import (
	"crypto/ed25519"

	"encoding/base64"
	"encoding/binary"
	"errors"
	"fmt"
	"strings"

	"golang.org/x/crypto/blake2b"
)

// Signatures are minisign-compatible (https://jedisct1.github.io/minisign/):
// the detached file <manifest>.sig is a minisign signature, so a manifest
// can be checked with `minisign -Vm manifest.json -P <public key>` and
// signed either with tools/release or with minisign itself (unencrypted or
// encrypted key; tools/release reads only unencrypted keys).
//
//	untrusted comment: <text>
//	base64(alg[2] | keyID[8] | ed25519 signature[64])
//	trusted comment: <text>
//	base64(ed25519 signature over signature[64] | trusted comment text)
//
// alg "ED" signs BLAKE2b-512(message) (minisign default), "Ed" signs the
// message itself (minisign -l, legacy). Both are verified; tools/release
// writes "ED". The public key is base64("Ed" | keyID[8] | key[32]).

const (
	algEd      = "Ed" // key algorithm, legacy (non-prehashed) signature
	algED      = "ED" // prehashed signature
	maxSigSize = 4096
)

// PublicKey is a parsed minisign public key.
type PublicKey struct {
	ID  [8]byte
	Key ed25519.PublicKey
}

// IDString is the key id as minisign prints it (little-endian uint64, hex).
func (k PublicKey) IDString() string { return keyIDString(k.ID) }

func keyIDString(id [8]byte) string {
	return fmt.Sprintf("%016X", binary.LittleEndian.Uint64(id[:]))
}

// ParsePublicKey accepts the base64 line or a whole minisign .pub file.
func ParsePublicKey(s string) (PublicKey, error) {
	var k PublicKey
	line := ""
	for _, l := range strings.Split(strings.TrimSpace(s), "\n") {
		l = strings.TrimSpace(l)
		if l == "" || strings.HasPrefix(l, "untrusted comment:") {
			continue
		}
		line = l
		break
	}
	b, err := base64.StdEncoding.DecodeString(line)
	if err != nil || len(b) != 2+8+32 || string(b[:2]) != algEd {
		return k, errors.New("invalid minisign public key")
	}
	copy(k.ID[:], b[2:10])
	k.Key = ed25519.PublicKey(append([]byte(nil), b[10:]...))
	return k, nil
}

// Encode returns the base64 line of a minisign public key.
func (k PublicKey) Encode() string {
	b := append([]byte(algEd), k.ID[:]...)
	return base64.StdEncoding.EncodeToString(append(b, k.Key...))
}

// Signature is a parsed minisign signature file.
type Signature struct {
	Alg            string
	KeyID          [8]byte
	Sig            []byte
	TrustedComment string
	GlobalSig      []byte
}

func ParseSignature(b []byte) (Signature, error) {
	var s Signature
	if len(b) > maxSigSize {
		return s, errors.New("signature file too large")
	}
	lines := strings.Split(strings.ReplaceAll(string(b), "\r\n", "\n"), "\n")
	if len(lines) < 4 || !strings.HasPrefix(lines[0], "untrusted comment:") || !strings.HasPrefix(lines[2], "trusted comment: ") {
		return s, errors.New("not a minisign signature")
	}
	raw, err := base64.StdEncoding.DecodeString(strings.TrimSpace(lines[1]))
	if err != nil || len(raw) != 2+8+64 {
		return s, errors.New("malformed signature line")
	}
	s.Alg = string(raw[:2])
	if s.Alg != algEd && s.Alg != algED {
		return s, errors.New("unsupported signature algorithm")
	}
	copy(s.KeyID[:], raw[2:10])
	s.Sig = raw[10:]
	s.TrustedComment = strings.TrimPrefix(lines[2], "trusted comment: ")
	s.GlobalSig, err = base64.StdEncoding.DecodeString(strings.TrimSpace(lines[3]))
	if err != nil || len(s.GlobalSig) != 64 {
		return s, errors.New("malformed global signature")
	}
	return s, nil
}

// Verify checks both the message signature and the trusted-comment
// signature with key k (the key id must match).
func (s Signature) Verify(k PublicKey, msg []byte) error {
	if s.KeyID != k.ID {
		return errors.New("signature key id does not match")
	}
	signed := msg
	if s.Alg == algED {
		h := blake2b.Sum512(msg)
		signed = h[:]
	}
	if !ed25519.Verify(k.Key, signed, s.Sig) {
		return errors.New("signature does not match the manifest")
	}
	if !ed25519.Verify(k.Key, append(append([]byte(nil), s.Sig...), s.TrustedComment...), s.GlobalSig) {
		return errors.New("trusted comment signature does not match")
	}
	return nil
}
