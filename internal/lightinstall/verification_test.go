package lightinstall

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/blake2b"
)

func TestSignedLightManifest(t *testing.T) {
	now := time.Date(2026, 11, 26, 18, 0, 0, 0, time.UTC)
	archive := Artifact{
		URL:       ReleaseBase + "/download/v3.5.11/" + ArchiveName("3.5.11", "arm64"),
		SizeBytes: 123,
		SHA256:    strings.Repeat("a", 64),
	}
	m := Manifest{1, Product, Channel, "3.5.11", now.Add(-time.Hour), now.Add(time.Hour),
		map[string]Artifact{"arm64": archive}}
	pk, sk, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	var id = []byte{1, 2, 3, 4, 5, 6, 7, 8}
	k := base64.StdEncoding.EncodeToString(append(append([]byte("Ed"), id...), pk...))
	sign := func(manifest Manifest) ([]byte, []byte) {
		data, err := json.Marshal(manifest)
		if err != nil {
			t.Fatal(err)
		}
		hash := blake2b.Sum512(data)
		sig := ed25519.Sign(sk, hash[:])
		packet := append(append([]byte("ED"), id...), sig...)
		comment := "release test"
		global := ed25519.Sign(sk, append(append([]byte(nil), sig...), comment...))
		detached := "untrusted comment: test\n" + base64.StdEncoding.EncodeToString(packet) +
			"\ntrusted comment: " + comment + "\n" + base64.StdEncoding.EncodeToString(global) + "\n"
		return data, []byte(detached)
	}
	data, sig := sign(m)
	info, err := signedManifest(data, sig, k, now, "arm64")
	if err != nil || !info.Available || info.Version != "3.5.11" || info.Archive != archive {
		t.Fatalf("signed Light manifest: %+v, %v", info, err)
	}
	for _, candidate := range []struct {
		name  string
		alter func(*Manifest)
	}{
		{"full BROray product", func(m *Manifest) { m.Product = "BROray" }},
		{"expired", func(m *Manifest) { m.ExpiresAt = now }},
		{"prerelease", func(m *Manifest) { m.Version += "-dev" }},
		{"foreign repository", func(m *Manifest) {
			m.Archives["arm64"] = Artifact{URL: "https://github.com/BROadmin/BROray/releases/asset", SizeBytes: 123, SHA256: archive.SHA256}
		}},
	} {
		t.Run(candidate.name, func(t *testing.T) {
			bad := m
			bad.Archives = map[string]Artifact{"arm64": archive}
			candidate.alter(&bad)
			data, sig := sign(bad)
			if _, err := signedManifest(data, sig, k, now, "arm64"); err == nil {
				t.Fatalf("accepted %s", candidate.name)
			}
		})
	}
	data = append(data, ' ')
	if _, err := signedManifest(data, sig, k, now, "arm64"); err == nil {
		t.Fatal("accepted changed bytes with original signature")
	}
	if _, err := signedManifest(data[:len(data)-1], sig, stableKey, now, "arm64"); err == nil {
		t.Fatal("accepted manifest signed by foreign key")
	}
}

func TestUnpackLightCandidate(t *testing.T) {
	type member struct {
		name string
		body string
		kind byte
	}
	valid := []member{
		{BinaryName, "test binary", tar.TypeReg},
		{"VERSION", "3.5.11\n", tar.TypeReg},
		{"LICENSE", "license", tar.TypeReg},
	}
	makeArchive := func(entries []member) []byte {
		var out bytes.Buffer
		gz := gzip.NewWriter(&out)
		tw := tar.NewWriter(gz)
		for _, e := range entries {
			h := &tar.Header{Name: e.name, Mode: 0o755, Size: int64(len(e.body)), Typeflag: e.kind}
			if err := tw.WriteHeader(h); err != nil {
				t.Fatal(err)
			}
			if _, err := tw.Write([]byte(e.body)); err != nil {
				t.Fatal(err)
			}
		}
		if err := tw.Close(); err != nil {
			t.Fatal(err)
		}
		if err := gz.Close(); err != nil {
			t.Fatal(err)
		}
		return out.Bytes()
	}
	var binary bytes.Buffer
	if err := unpackCandidate(bytes.NewReader(makeArchive(valid)), &binary, "3.5.11"); err != nil || binary.String() != "test binary" {
		t.Fatalf("unpack: got %q, %v", &binary, err)
	}
	for _, bad := range []member{
		{"../broray-light", "data", tar.TypeReg},
		{"LICENSES/fake.txt", "", tar.TypeSymlink},
		{BinaryName, "duplicate", tar.TypeReg},
	} {
		binary.Reset()
		if err := unpackCandidate(bytes.NewReader(makeArchive(append(append([]member(nil), valid...), bad))), &binary, "3.5.11"); err == nil {
			t.Fatalf("accepted archive member %+v", bad)
		}
	}
	binary.Reset()
	if err := unpackCandidate(bytes.NewReader(makeArchive(valid)), &binary, "3.5.12"); err == nil {
		t.Fatal("accepted archive for a different version")
	}
}
