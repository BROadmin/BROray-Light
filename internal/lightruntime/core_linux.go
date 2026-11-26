package lightruntime

import (
	"archive/zip"
	"context"
	"crypto/sha256"
	"debug/elf"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"time"

	"github.com/BROadmin/broray-light/internal/lightstate"
	"github.com/BROadmin/broray-light/modules/servers"
)

const CoreRelease = "26.11.9"
const maxCoreZIP = 32 << 20
const maxCoreELF = 72 << 20

type coreAsset struct {
	file, digest string
	machine      elf.Machine
	data         elf.Data
}

// XTLS GitHub release asset digests. Also present in the pinned BROray donor.
var coreAssets = map[string]coreAsset{
	"arm64":  {"Xray-linux-arm64-v8a.zip", "64ed6858982a7f5eb85d88b811089063bd4f17561f4c8f44e0f1dc8e6f6430be", elf.EM_AARCH64, elf.ELFDATA2LSB},
	"arm":    {"Xray-linux-arm32-v7a.zip", "19c51e08a6562705fb1cb032a84fd87df21d7e27b194f035be7e754dbe3a97b3", elf.EM_ARM, elf.ELFDATA2LSB},
	"mipsle": {"Xray-linux-mips32le.zip", "793dc40029283eb9ccead188b05abf0d34b64aab16ad1f6eadd204963a54837b", elf.EM_MIPS, elf.ELFDATA2LSB},
	"mips":   {"Xray-linux-mips32.zip", "4ceb213ad7cd8c1fc9250bb886e730665cddb9dfe891291b09231a204f8ba6ef", elf.EM_MIPS, elf.ELFDATA2MSB},
	"amd64":  {"Xray-linux-64.zip", "b651f7e1d9966ee2c1b1ee1bf8b52c72771824d3065dce96bbc8bcc19ed95f82", elf.EM_X86_64, elf.ELFDATA2LSB},
}

var xrayVersion = regexp.MustCompile(`^Xray ([0-9]+\.[0-9]+\.[0-9]+)\b`)

func (r *Runtime) CoreVersion(ctx context.Context) (string, error) {
	if _, err := os.Lstat(r.binary); errors.Is(err, os.ErrNotExist) {
		return "", nil
	} else if err != nil {
		return "", err
	}
	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	data, err := r.command(ctx, "version").Output()
	if err != nil {
		return "", errors.New("installed Xray version is unavailable")
	}
	match := xrayVersion.FindSubmatch(data)
	if len(match) != 2 {
		return "", errors.New("unrecognized Xray version")
	}
	return string(match[1]), nil
}

func prepareCore(ctx context.Context, dir, run string, asset coreAsset) (string, error) {
	const base = "https://github.com/XTLS/Xray-core/releases/download/v" + CoreRelease + "/"
	httpClient := &http.Client{Timeout: 2 * time.Minute, CheckRedirect: func(req *http.Request, history []*http.Request) error {
		host := req.URL.Host
		if len(history) > 5 || req.URL.Scheme != "https" || (host != "release-assets.githubusercontent.com" && host != "objects.githubusercontent.com" && (host != "github.com" || !strings.HasPrefix(req.URL.String(), base))) {
			return errors.New("untrusted Xray download redirect")
		}
		return nil
	}}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, base+asset.file, nil)
	if err != nil {
		return "", err
	}
	response, err := httpClient.Do(req)
	if err != nil {
		return "", errors.New("Xray archive download failed")
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK || response.ContentLength > maxCoreZIP {
		return "", errors.New("Xray archive request failed")
	}
	archive, err := os.CreateTemp(run, "core-download-*.zip")
	if err != nil {
		return "", err
	}
	defer os.Remove(archive.Name())
	defer archive.Close()
	digest := sha256.New()
	n, err := io.Copy(io.MultiWriter(archive, digest), io.LimitReader(response.Body, maxCoreZIP+1))
	if err != nil || n > maxCoreZIP || hex.EncodeToString(digest.Sum(nil)) != asset.digest {
		return "", errors.New("Xray archive digest or size mismatch")
	}
	reader, err := zip.NewReader(archive, n)
	if err != nil {
		return "", err
	}
	var core *zip.File
	for _, member := range reader.File {
		if member.Name != "xray" {
			continue
		}
		if core != nil || !member.Mode().IsRegular() || member.UncompressedSize64 > maxCoreELF {
			return "", errors.New("invalid Xray member")
		}
		core = member
	}
	if core == nil {
		return "", errors.New("Xray executable is absent in archive")
	}
	source, err := core.Open()
	if err != nil {
		return "", err
	}
	defer source.Close()
	staged, err := os.CreateTemp(dir, ".xray-candidate-")
	if err != nil {
		return "", err
	}
	path := staged.Name()
	keep := false
	defer func() {
		_ = staged.Close()
		if !keep {
			_ = os.Remove(path)
		}
	}()
	n, err = io.Copy(staged, io.LimitReader(source, maxCoreELF+1))
	if err != nil || uint64(n) != core.UncompressedSize64 {
		return "", errors.New("Xray member failed validation")
	}
	inspected, err := elf.NewFile(staged)
	if err != nil {
		return "", err
	}
	if inspected.Machine != asset.machine || inspected.Data != asset.data {
		return "", errors.New("Xray executable architecture mismatch")
	}
	for _, program := range inspected.Progs {
		if program.Type == elf.PT_INTERP {
			return "", errors.New("Xray executable is dynamically linked")
		}
	}
	if err := staged.Chmod(0700); err != nil {
		return "", err
	}
	if err := staged.Sync(); err != nil {
		return "", err
	}
	if err := staged.Close(); err != nil {
		return "", err
	}
	keep = true
	return path, nil
}

type coreTransaction struct {
	Previous  bool `json:"previous"`
	Committed bool `json:"committed"`
}

func (r *Runtime) recordCore(tx coreTransaction) error {
	payload, err := json.Marshal(tx)
	if err != nil {
		return err
	}
	_, err = lightstate.AtomicWrite(r.binary+".transaction", payload)
	return err
}

func removeIfPresent(path string) error {
	err := os.Remove(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	return err
}

func (r *Runtime) RecoverCore() error {
	prev := r.binary + ".previous"
	journal := r.binary + ".transaction"
	data, err := os.ReadFile(journal)
	if errors.Is(err, os.ErrNotExist) {
		old, err := os.Lstat(prev)
		if errors.Is(err, os.ErrNotExist) {
			return nil
		}
		if err != nil {
			return err
		}
		current, err := os.Lstat(r.binary)
		if err != nil || !old.Mode().IsRegular() || !os.SameFile(old, current) {
			return errors.New("Xray rollback evidence requires inspection")
		}
		return removeIfPresent(prev)
	}
	if err != nil {
		return err
	}
	var tx coreTransaction
	if err := json.Unmarshal(data, &tx); err != nil {
		return err
	}
	if !tx.Committed {
		if tx.Previous {
			rollback := r.binary + ".rollback"
			if err := removeIfPresent(rollback); err != nil {
				return err
			}
			if err := os.Link(prev, rollback); err != nil {
				return err
			}
			if err := os.Rename(rollback, r.binary); err != nil {
				return err
			}
			if err := removeIfPresent(rollback); err != nil {
				return err
			}
		} else if err := removeIfPresent(r.binary); err != nil {
			return err
		}
		tx.Committed = true
		if err := r.recordCore(tx); err != nil {
			return err
		}
	}
	if err := removeIfPresent(prev); err != nil {
		return err
	}
	if err := removeIfPresent(journal); err != nil {
		return err
	}
	dir, err := os.Open(filepath.Dir(r.binary))
	if err != nil {
		return err
	}
	defer dir.Close()
	return dir.Sync()
}

// InstallCore stages an upstream archive in RAM, verifies the candidate and
// keeps the previous inode until the caller confirms the active connection.
func (r *Runtime) InstallCore(ctx context.Context, selected *servers.Server, restart func(context.Context) error) error {
	asset, ok := coreAssets[runtime.GOARCH]
	if !ok {
		return errors.New("unsupported Xray architecture")
	}
	dir := filepath.Dir(r.binary)
	for _, leaf := range []string{filepath.Dir(dir), dir} {
		if err := os.Mkdir(leaf, 0700); err != nil && !errors.Is(err, os.ErrExist) {
			return err
		}
		info, err := os.Lstat(leaf)
		if err != nil || !info.IsDir() || info.Mode().Perm()&0022 != 0 {
			return errors.New("unsafe Xray installation directory")
		}
	}
	if err := r.RecoverCore(); err != nil {
		return err
	}
	path, err := prepareCore(ctx, dir, r.run, asset)
	if err != nil {
		return err
	}
	defer removeIfPresent(path)
	candidate := New(path, r.run, r.address, r.probeURL)
	version, err := candidate.CoreVersion(ctx)
	if err != nil || version != CoreRelease {
		return errors.New("Xray candidate did not identify as the pinned release")
	}
	if selected != nil {
		if err := candidate.Check(ctx, *selected); err != nil {
			return fmt.Errorf("Xray candidate connection: %w", err)
		}
	}
	old, err := os.Lstat(r.binary)
	tx := coreTransaction{Previous: err == nil}
	if tx.Previous {
		if !old.Mode().IsRegular() {
			return errors.New("existing Xray executable is not a regular file")
		}
		if err := os.Link(r.binary, r.binary+".previous"); err != nil {
			return err
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return err
	}
	if err := r.recordCore(tx); err != nil {
		return err
	}
	if err := os.Rename(path, r.binary); err != nil {
		return errors.Join(err, r.RecoverCore())
	}
	if err := restart(ctx); err != nil {
		rollback, cancel := context.WithTimeout(context.Background(), 35*time.Second)
		defer cancel()
		if recovery := r.RecoverCore(); recovery != nil {
			return errors.Join(err, recovery)
		}
		return errors.Join(err, restart(rollback))
	}
	tx.Committed = true
	if err := r.recordCore(tx); err != nil {
		return err
	}
	return r.RecoverCore()
}
