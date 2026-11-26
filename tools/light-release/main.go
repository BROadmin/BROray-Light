// light-release builds the four static Linux distributions.
package main

import (
	"archive/tar"
	"compress/gzip"
	"crypto/sha256"
	"debug/buildinfo"
	"debug/elf"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/BROadmin/broray-light/internal/lightinstall"
)

type target struct {
	platform string
	arch     string
	tuning   string
	machine  elf.Machine
	order    elf.Data
	class    elf.Class
}

var targets = []target{
	{"arm64", "arm64", "GOARM64=v8.0", elf.EM_AARCH64, elf.ELFDATA2LSB, elf.ELFCLASS64},
	{"armv7", "arm", "GOARM=7", elf.EM_ARM, elf.ELFDATA2LSB, elf.ELFCLASS32},
	{"mipsel", "mipsle", "GOMIPS=softfloat", elf.EM_MIPS, elf.ELFDATA2LSB, elf.ELFCLASS32},
	{"mips", "mips", "GOMIPS=softfloat", elf.EM_MIPS, elf.ELFDATA2MSB, elf.ELFCLASS32},
}

type notice struct {
	path  string
	entry string
}

var notices = []notice{
	{"LICENSE", "LICENSE"},
	{"vendor/go.yaml.in/yaml/v3/LICENSE", "LICENSES/go.yaml.in-yaml-v3-LICENSE.txt"},
	{"vendor/go.yaml.in/yaml/v3/NOTICE", "LICENSES/go.yaml.in-yaml-v3-NOTICE.txt"},
	{"vendor/golang.org/x/crypto/LICENSE", "LICENSES/golang.org-x-crypto-LICENSE.txt"},
	{"vendor/golang.org/x/sys/LICENSE", "LICENSES/golang.org-x-sys-LICENSE.txt"},
}

func main() {
	out := flag.String("out", "", "new release output directory")
	issued := flag.String("issued", "", "optional RFC3339 issue time for an unsigned release manifest")
	expires := flag.String("expires", "", "optional RFC3339 expiry time for an unsigned release manifest")
	flag.Parse()
	if err := build(*out, *issued, *expires); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func build(out, issued, expires string) error {
	if out == "" || flag.NArg() != 0 {
		return errors.New("usage: go run ./tools/light-release -out NEW_DIRECTORY")
	}
	if runtime.Version() != "go1.24.13" {
		return fmt.Errorf("release toolchain: expected Go 1.24.13, got %s", runtime.Version())
	}
	manifest := lightinstall.Manifest{
		SchemaVersion: 1,
		Product:       lightinstall.Product,
		Channel:       lightinstall.Channel,
		Version:       lightinstall.Version,
		Archives:      make(map[string]lightinstall.Artifact),
	}
	writeManifest := issued != "" || expires != ""
	if writeManifest {
		var err error
		manifest.IssuedAt, err = time.Parse(time.RFC3339, issued)
		if err != nil {
			return fmt.Errorf("issue time: %w", err)
		}
		manifest.ExpiresAt, err = time.Parse(time.RFC3339, expires)
		if err != nil {
			return fmt.Errorf("expiry time: %w", err)
		}
		if !manifest.ExpiresAt.After(manifest.IssuedAt) {
			return errors.New("expiry must be after the issue time")
		}
	}
	if err := os.Mkdir(out, 0o755); err != nil {
		return err
	}
	raw := filepath.Join(out, "binaries")
	if err := os.Mkdir(raw, 0o755); err != nil {
		return err
	}
	var archiveSums, binarySums, sizes strings.Builder
	sizes.WriteString("platform\tbinary_bytes\tarchive_bytes\n")
	for _, t := range targets {
		if err := t.build(raw, out, &manifest, &archiveSums, &binarySums, &sizes); err != nil {
			return err
		}
	}
	for _, output := range []struct{ file, content string }{
		{"SHA256SUMS", archiveSums.String()},
		{"SHA256SUMS.binaries", binarySums.String()},
		{"SIZES.tsv", sizes.String()},
	} {
		if err := os.WriteFile(filepath.Join(out, output.file), []byte(output.content), 0o644); err != nil {
			return err
		}
	}
	if writeManifest {
		data, err := json.MarshalIndent(manifest, "", "  ")
		if err != nil {
			return err
		}
		return os.WriteFile(filepath.Join(out, lightinstall.ManifestName), append(data, '\n'), 0o644)
	}
	return nil
}

func (t target) build(raw, out string, manifest *lightinstall.Manifest, archiveSums, binarySums, sizes *strings.Builder) error {
	subdir := filepath.Join(raw, t.platform)
	if err := os.Mkdir(subdir, 0o755); err != nil {
		return err
	}
	binaryPath := filepath.Join(subdir, lightinstall.BinaryName)
	cmd := exec.Command(filepath.Join(runtime.GOROOT(), "bin", "go"), "build",
		"-mod=vendor", "-trimpath", "-buildvcs=false", "-ldflags=-s -w -buildid=", "-o", binaryPath, "./cmd/broray-light")
	cmd.Env = buildEnvironment(t)
	cmd.Stdout, cmd.Stderr = os.Stdout, os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("build linux/%s: %w", t.platform, err)
	}
	if err := verifyELF(binaryPath, t); err != nil {
		return fmt.Errorf("verify linux/%s: %w", t.platform, err)
	}
	archive := lightinstall.ArchiveName(lightinstall.Version, t.platform)
	dest := filepath.Join(out, archive)
	if err := pack(dest, binaryPath); err != nil {
		return err
	}
	binaryHash, binaryBytes, err := digest(binaryPath)
	if err != nil {
		return err
	}
	archiveHash, archiveBytes, err := digest(dest)
	if err != nil {
		return err
	}
	manifest.Archives[t.platform] = lightinstall.Artifact{
		URL:       lightinstall.ReleaseBase + "/download/v" + lightinstall.Version + "/" + archive,
		SizeBytes: archiveBytes,
		SHA256:    archiveHash,
	}
	fmt.Fprintf(archiveSums, "%s  %s\n", archiveHash, archive)
	fmt.Fprintf(binarySums, "%s  binaries/%s/%s\n", binaryHash, t.platform, lightinstall.BinaryName)
	fmt.Fprintf(sizes, "%s\t%d\t%d\n", t.platform, binaryBytes, archiveBytes)
	fmt.Printf("%s: %d binary bytes, %d archive bytes\n", t.platform, binaryBytes, archiveBytes)
	return nil
}

func buildEnvironment(t target) []string {
	drop := map[string]bool{
		"GOOS": true, "GOARCH": true, "CGO_ENABLED": true, "GOARM": true, "GOARM64": true,
		"GOMIPS": true, "GOAMD64": true, "GOMIPS64": true, "GOTOOLCHAIN": true, "GOEXPERIMENT": true,
		"GOWORK": true, "GOFLAGS": true, "GOENV": true, "GOROOT": true,
	}
	var env []string
	for _, setting := range os.Environ() {
		key, _, _ := strings.Cut(setting, "=")
		if !drop[strings.ToUpper(key)] {
			env = append(env, setting)
		}
	}
	return append(env,
		"GOOS=linux", "GOARCH="+t.arch, t.tuning, "CGO_ENABLED=0", "GOTOOLCHAIN=local",
		"GOENV=off", "GOWORK=off", "GOFLAGS=", "GOEXPERIMENT=")
}

func verifyELF(name string, t target) error {
	bin, err := elf.Open(name)
	if err != nil {
		return err
	}
	defer bin.Close()
	if bin.Machine != t.machine || bin.Data != t.order || bin.Class != t.class || bin.Type != elf.ET_EXEC {
		return errors.New("unexpected ELF architecture")
	}
	for _, prog := range bin.Progs {
		if prog.Type == elf.PT_INTERP || prog.Type == elf.PT_DYNAMIC {
			return errors.New("dynamically linked build")
		}
	}
	info, err := buildinfo.ReadFile(name)
	if err != nil {
		return err
	}
	settings := make(map[string]string)
	for _, setting := range info.Settings {
		settings[setting.Key] = setting.Value
	}
	key, value, _ := strings.Cut(t.tuning, "=")
	if settings["GOOS"] != "linux" || settings["GOARCH"] != t.arch ||
		settings["CGO_ENABLED"] != "0" || settings[key] != value {
		return fmt.Errorf("unexpected Go target settings for %s", t.tuning)
	}
	return nil
}

func pack(dest, binary string) error {
	f, err := os.OpenFile(dest, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o644)
	if err != nil {
		return err
	}
	gz, err := gzip.NewWriterLevel(f, gzip.BestCompression)
	if err != nil {
		return errors.Join(err, f.Close())
	}
	tw := tar.NewWriter(gz)
	writeErr := writePackage(tw, binary)
	return errors.Join(writeErr, tw.Close(), gz.Close(), f.Close())
}

func writePackage(tw *tar.Writer, binary string) error {
	if err := addFile(tw, binary, lightinstall.BinaryName, 0o755); err != nil {
		return err
	}
	version := lightinstall.Version + "\n"
	if err := add(tw, "VERSION", 0o644, int64(len(version)), strings.NewReader(version)); err != nil {
		return err
	}
	if err := addFile(tw, filepath.Join(runtime.GOROOT(), "LICENSE"), "LICENSES/Go-LICENSE.txt", 0o644); err != nil {
		return err
	}
	origin := "BROray-Light " + lightinstall.Version + "\n" +
		"Selected source from BROadmin/BROray v3.5.10 (92dc010ebad5fd21dff9e625925e9847b3714640).\n" +
		"Build toolchain: " + runtime.Version() + ". Xray is a separate distribution.\n"
	if err := add(tw, "THIRD-PARTY-NOTICES.txt", 0o644, int64(len(origin)), strings.NewReader(origin)); err != nil {
		return err
	}
	for _, notice := range notices {
		if err := addFile(tw, notice.path, notice.entry, 0o644); err != nil {
			return err
		}
	}
	return nil
}

func addFile(w *tar.Writer, path, name string, mode int64) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()
	st, err := f.Stat()
	if err != nil {
		return err
	}
	return add(w, name, mode, st.Size(), f)
}

func add(w *tar.Writer, name string, mode, size int64, body io.Reader) error {
	h := tar.Header{Name: name, Mode: mode, Size: size, Typeflag: tar.TypeReg, Format: tar.FormatUSTAR, ModTime: time.Unix(0, 0).UTC()}
	if err := w.WriteHeader(&h); err != nil {
		return err
	}
	_, err := io.Copy(w, body)
	return err
}

func digest(path string) (string, int64, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", 0, err
	}
	defer f.Close()
	h := sha256.New()
	size, err := io.Copy(h, f)
	return hex.EncodeToString(h.Sum(nil)), size, err
}
