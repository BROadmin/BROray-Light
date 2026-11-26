package lightinstall

import (
	"archive/tar"
	"compress/gzip"
	"errors"
	"fmt"
	"io"
	"path"
	"strings"
)

const BinaryName = "broray-light"

func unpackCandidate(input io.Reader, binary io.Writer, version string) error {
	gz, err := gzip.NewReader(input)
	if err != nil {
		return err
	}
	defer gz.Close()

	tr := tar.NewReader(gz)
	seen := make(map[string]bool)
	var totalSize int64
	for {
		h, err := tr.Next()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return err
		}
		name := h.Name
		if len(name) == 0 || name != path.Clean(name) || strings.ContainsAny(name, "\\\x00") ||
			seen[name] || h.Typeflag != tar.TypeReg || h.Size < 0 || h.Size > maxArchive-totalSize ||
			len(seen) >= 24 {
			return fmt.Errorf("invalid archive entry %q", name)
		}
		seen[name] = true
		totalSize += h.Size
		switch name {
		case BinaryName:
			if h.Size == 0 || h.Mode&0o111 == 0 {
				return errors.New("archive does not contain an executable Light binary")
			}
			if _, err := io.Copy(binary, tr); err != nil {
				return err
			}
		case "VERSION":
			data, err := io.ReadAll(io.LimitReader(tr, 64))
			if err != nil || h.Size > 64 || string(data) != version+"\n" {
				return errors.New("archive version does not match the signed release")
			}
		case "LICENSE", "THIRD-PARTY-NOTICES.txt":
			// Distribution notices are not runtime files.
		default:
			if path.Dir(name) != "LICENSES" || !strings.HasSuffix(name, ".txt") {
				return fmt.Errorf("unexpected archive entry %q", name)
			}
		}
	}
	if !seen[BinaryName] || !seen["VERSION"] || !seen["LICENSE"] {
		return errors.New("incomplete BROray-Light archive")
	}
	// Read through the gzip terminator to validate its checksum. tar.Reader
	// stops at the tar terminator and can leave the gzip trailer unread.
	n, err := io.Copy(io.Discard, io.LimitReader(gz, 1))
	if err != nil {
		return err
	}
	if n != 0 {
		return errors.New("unexpected data after archive terminator")
	}
	return nil
}
