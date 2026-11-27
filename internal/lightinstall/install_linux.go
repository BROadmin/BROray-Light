package lightinstall

import (
	"bytes"
	"context"
	"crypto/sha256"
	_ "embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"golang.org/x/sys/unix"
)

const (
	DefaultRoot    = "/opt/broray-light"
	DefaultRun     = "/tmp/broray-light/run"
	DefaultInitDir = "/opt/etc/init.d"
	initName       = "S24broray-light"
	initMarker     = "# BROray-Light Go init v1\n"
	receiptName    = ".light-go-install.json"
)

//go:embed init.sh
var initScript string

type layout struct {
	root        string
	run         string
	init        string
	restoreOnly bool
}

func (l layout) binary() string      { return filepath.Join(l.root, "bin", BinaryName) }
func (l layout) service() string     { return filepath.Join(l.init, initName) }
func (l layout) installed() string   { return filepath.Join(l.root, ".light-go-version") }
func (l layout) rollbackDir() string { return filepath.Join(l.root, ".light-go-install") }
func (l layout) receiptPath() string { return filepath.Join(l.root, receiptName) }

func flags(command string, args []string) (layout, string, string, error) {
	fs := flag.NewFlagSet(command, flag.ContinueOnError)
	root := fs.String("root", DefaultRoot, "BROray-Light installation root")
	run := fs.String("run", DefaultRun, "BROray-Light volatile state directory")
	init := fs.String("init-dir", DefaultInitDir, "Entware init script directory")
	var restoreOnly bool
	if command == "recover" {
		fs.BoolVar(&restoreOnly, "restore-only", false, "restore files for the init script without starting the daemon")
	}
	var binary, hash *string
	if command == "install" {
		binary = fs.String("binary", "", "binary to install (default is the invoked executable)")
		hash = fs.String("sha256", "", "expected SHA-256 of the local binary")
	}
	if err := fs.Parse(args); err != nil {
		return layout{}, "", "", err
	}
	if fs.NArg() != 0 {
		return layout{}, "", "", errors.New("unexpected installer arguments")
	}
	l := layout{root: *root, run: *run, init: *init, restoreOnly: restoreOnly}
	for _, dir := range []string{l.root, l.run, l.init} {
		if strings.ContainsAny(dir, "\r\n\x00") || !filepath.IsAbs(dir) ||
			dir != filepath.Clean(dir) || dir == "/" {
			return layout{}, "", "", errors.New("installer directories must use clean absolute paths")
		}
	}
	if l.root == l.run || l.root == l.init || l.run == l.init {
		return layout{}, "", "", errors.New("installation, runtime and init directories must differ")
	}
	if binary == nil {
		return l, "", "", nil
	}
	if !validHash(*hash) {
		return layout{}, "", "", errors.New("install requires the expected lowercase --sha256 of the binary")
	}
	if *binary == "" {
		own, err := os.Executable()
		if err != nil {
			return layout{}, "", "", err
		}
		*binary = own
	}
	return l, *binary, *hash, nil
}

func Run(args []string) error {
	if len(args) == 0 {
		return errors.New("expected install, update or recover")
	}
	command := args[0]
	if command != "install" && command != "update" && command != "recover" {
		return errors.New("unsupported installer command")
	}
	l, binary, digest, err := flags(command, args[1:])
	if err != nil {
		return err
	}
	if err := l.prepare(); err != nil {
		return err
	}
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	lockCtx, cancelLock := context.WithTimeout(ctx, 2*time.Minute)
	lock, err := waitOperationLock(lockCtx, l.run)
	cancelLock()
	if err != nil {
		return err
	}
	defer lock.Close()

	if err := l.recover(ctx, !l.restoreOnly); err != nil {
		return fmt.Errorf("recover previous installation: %w", err)
	}
	switch command {
	case "install":
		return l.installLocal(ctx, binary, digest)
	case "update":
		return l.update(ctx)
	default:
		return nil
	}
}

func exists(path string) (bool, error) {
	_, err := os.Lstat(path)
	if errors.Is(err, os.ErrNotExist) {
		return false, nil
	}
	return err == nil, err
}

func localFile(path string) (*os.File, error) {
	fd, err := unix.Open(path, unix.O_RDONLY|unix.O_CLOEXEC|unix.O_NOFOLLOW|unix.O_NONBLOCK, 0)
	if err != nil {
		return nil, err
	}
	f := os.NewFile(uintptr(fd), path)
	st, err := f.Stat()
	if err != nil || !st.Mode().IsRegular() {
		f.Close()
		if err != nil {
			return nil, err
		}
		return nil, fmt.Errorf("expected regular file %s", path)
	}
	return f, nil
}

func readLocal(path string, max int64) ([]byte, error) {
	f, err := localFile(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	data, err := io.ReadAll(io.LimitReader(f, max+1))
	if err == nil && int64(len(data)) > max {
		return nil, fmt.Errorf("%s exceeds size limit", path)
	}
	return data, err
}

func trustedDir(path string, mode os.FileMode) error {
	if err := os.MkdirAll(path, mode); err != nil {
		return err
	}
	st, err := os.Lstat(path)
	if err != nil {
		return err
	}
	s := st.Sys().(*syscall.Stat_t)
	if !st.IsDir() || s.Uid != uint32(os.Geteuid()) || st.Mode().Perm()&0o022 != 0 ||
		(mode == 0o700 && st.Mode().Perm() != mode) {
		return fmt.Errorf("unsafe directory %s", path)
	}
	return nil
}

func (l layout) prepare() error {
	for _, path := range []string{filepath.Join(filepath.Dir(l.root), "broray"),
		filepath.Join(l.init, "S24broray"), filepath.Join(l.init, "S25broray")} {
		yes, err := exists(path)
		if err != nil {
			return err
		}
		if yes {
			return fmt.Errorf("full BROray installation conflicts with BROray-Light (%s)", path)
		}
	}
	// The legacy Light uses a different updater, service and state format.
	for _, path := range []string{filepath.Join(l.root, "bin", "broray-lightd"),
		filepath.Join(l.root, "current"), filepath.Join(l.init, "S23broray-light-updater")} {
		yes, err := exists(path)
		if err != nil {
			return err
		}
		if yes {
			return fmt.Errorf("legacy BROray-Light detected at %s; export settings before migrating", path)
		}
	}
	if err := trustedDir(l.init, 0o755); err != nil {
		return err
	}
	if _, err := l.ownsInit(); err != nil {
		return err
	}
	if err := trustedDir(l.root, 0o755); err != nil {
		return err
	}
	if err := trustedDir(filepath.Dir(l.binary()), 0o755); err != nil {
		return err
	}
	if err := trustedDir(filepath.Dir(l.run), 0o700); err != nil {
		return err
	}
	return trustedDir(l.run, 0o700)
}

// TryOperationLock takes the installer lock without blocking, for router writes
// that must not cross an installation or update.
func TryOperationLock(run string) (io.Closer, error) {
	f, err := lockFile(run)
	if err != nil {
		return nil, err
	}
	return f, nil
}

func waitOperationLock(ctx context.Context, run string) (*os.File, error) {
	retry := time.NewTicker(time.Second)
	defer retry.Stop()
	for ctx.Err() == nil {
		f, err := lockFile(run)
		if !errors.Is(err, unix.EWOULDBLOCK) {
			return f, err
		}
		select {
		case <-ctx.Done():
		case <-retry.C:
		}
	}
	return nil, fmt.Errorf("waiting for the installer lock: %w", ctx.Err())
}

func lockFile(dir string) (*os.File, error) {
	path := filepath.Join(dir, "install.lock")
	fd, err := unix.Open(path, unix.O_RDWR|unix.O_CREAT|unix.O_CLOEXEC|unix.O_NOFOLLOW, 0o600)
	if err != nil {
		return nil, err
	}
	f := os.NewFile(uintptr(fd), path)
	st, err := f.Stat()
	if err != nil {
		f.Close()
		return nil, err
	}
	if !st.Mode().IsRegular() || st.Mode().Perm() != 0o600 || st.Sys().(*syscall.Stat_t).Uid != uint32(os.Geteuid()) {
		f.Close()
		return nil, errors.New("invalid installer lock")
	}
	if err := unix.Flock(fd, unix.LOCK_EX|unix.LOCK_NB); err != nil {
		f.Close()
		return nil, fmt.Errorf("installer or updater is already running: %w", err)
	}
	return f, nil
}

func (l layout) ownsInit() (bool, error) {
	data, err := readLocal(l.service(), 64<<10)
	if errors.Is(err, os.ErrNotExist) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if !bytes.HasPrefix(data, []byte("#!/bin/sh\n"+initMarker)) {
		return false, fmt.Errorf("unknown init service at %s; legacy or foreign installation", l.service())
	}
	return true, nil
}

func shellQuote(s string) string { return "'" + strings.ReplaceAll(s, "'", "'\\''") + "'" }

func (l layout) serviceBody() []byte {
	r := strings.NewReplacer("@ROOT@", shellQuote(l.root), "@RUN@", shellQuote(l.run), "@INIT@", shellQuote(l.init))
	return []byte(r.Replace(strings.ReplaceAll(initScript, "\r\n", "\n")))
}

func syncDir(path string) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()
	return f.Sync()
}

func atomicFile(path string, mode os.FileMode, input io.Reader) error {
	dir := filepath.Dir(path)
	f, err := os.CreateTemp(dir, ".install-*")
	if err != nil {
		return err
	}
	defer os.Remove(f.Name())
	_, copyErr := io.Copy(f, input)
	if err := errors.Join(copyErr, f.Chmod(mode), f.Sync(), f.Close()); err != nil {
		return err
	}
	if err := os.Rename(f.Name(), path); err != nil {
		return err
	}
	return syncDir(dir)
}

func copyFile(src, dest string, mode os.FileMode) error {
	f, err := localFile(src)
	if err != nil {
		return err
	}
	defer f.Close()
	return atomicFile(dest, mode, f)
}

func removeFile(path string) error {
	if err := os.Remove(path); err != nil && !errors.Is(err, os.ErrNotExist) {
		return err
	}
	return syncDir(filepath.Dir(path))
}

func (l layout) serviceCmd(ctx context.Context, arg string) error {
	cmd := exec.CommandContext(ctx, "/bin/sh", l.service(), arg)
	data, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("service %s: %w %s", arg, err, strings.TrimSpace(string(data)))
	}
	return nil
}

func (l layout) probeReady(ctx context.Context, version string, serviceOnly bool) ([]byte, error) {
	ctx, cancel := context.WithTimeout(ctx, 12*time.Second)
	defer cancel()
	args := []string{"ready", "--root", l.root, "--run", l.run, "--version", version}
	if serviceOnly {
		args = append(args, "--service-only")
	}
	return exec.CommandContext(ctx, l.binary(), args...).CombinedOutput()
}

func (l layout) waitReady(ctx context.Context, version string, serviceOnly bool) error {
	ctx, cancel := context.WithTimeout(ctx, 2*time.Minute)
	defer cancel()
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	for {
		out, err := l.probeReady(ctx, version, serviceOnly)
		if err == nil {
			return nil
		}
		if serviceOnly && bytes.HasPrefix(out, []byte("flag provided but not defined: -service-only\n")) {
			serviceOnly = false
			continue
		}
		select {
		case <-ctx.Done():
			return fmt.Errorf("installed service did not confirm readiness: %w: %s", ctx.Err(), strings.TrimSpace(string(out)))
		case <-ticker.C:
		}
	}
}

type receipt struct {
	PreviousVersion string `json:"previousVersion"`
	PreviousRunning bool   `json:"previousRunning"`
	Committed       bool   `json:"committed"`
}

func (l layout) record(r receipt) error {
	data, err := json.Marshal(r)
	if err != nil {
		return err
	}
	return atomicFile(l.receiptPath(), 0o600, bytes.NewReader(data))
}

func (l layout) currentVersion() (string, error) {
	b, err := readLocal(l.installed(), 64)
	if errors.Is(err, os.ErrNotExist) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	version := strings.TrimSpace(string(b))
	if _, err := versionParts(version); err != nil {
		return "", err
	}
	return version, nil
}

// finish removes private, completed transaction records. A cleanup failure
// leaves the receipt intact so recover can safely retry on the next request.
func (l layout) finish() error {
	dir := l.rollbackDir()
	present, err := exists(dir)
	if err != nil {
		return err
	}
	if present {
		if err := trustedDir(dir, 0o700); err != nil {
			return err
		}
		for _, name := range []string{"binary", "service"} {
			if err := removeFile(filepath.Join(dir, name)); err != nil {
				return err
			}
		}
		// If staging was interrupted before an atomic backup rename, these
		// invocation-owned files may still be inside the private directory.
		files, err := os.ReadDir(dir)
		if err != nil {
			return err
		}
		for _, file := range files {
			if file.Type() != 0 || !strings.HasPrefix(file.Name(), ".install-") {
				return fmt.Errorf("unexpected entry in installer backup: %s", file.Name())
			}
			if err := removeFile(filepath.Join(dir, file.Name())); err != nil {
				return err
			}
		}
		if err := removeFile(dir); err != nil {
			return err
		}
	}
	return removeFile(l.receiptPath())
}

func (l layout) restore(ctx context.Context, r receipt, restart bool) error {
	owned, err := l.ownsInit()
	if err != nil {
		return err
	}
	if owned {
		if err := l.serviceCmd(ctx, "stop"); err != nil {
			return err
		}
	}
	if r.PreviousVersion == "" {
		return errors.Join(removeFile(l.service()), removeFile(l.binary()), removeFile(l.installed()))
	}
	dir := l.rollbackDir()
	if err := trustedDir(dir, 0o700); err != nil {
		return err
	}
	if err := copyFile(filepath.Join(dir, "binary"), l.binary(), 0o755); err != nil {
		return err
	}
	if err := copyFile(filepath.Join(dir, "service"), l.service(), 0o755); err != nil {
		return err
	}
	if err := atomicFile(l.installed(), 0o600, strings.NewReader(r.PreviousVersion+"\n")); err != nil {
		return err
	}
	if r.PreviousRunning && restart {
		if err := l.serviceCmd(ctx, "start-installed"); err != nil {
			return err
		}
		return l.waitReady(ctx, r.PreviousVersion, true)
	}
	return nil
}

func (l layout) recover(ctx context.Context, restart bool) error {
	data, err := readLocal(l.receiptPath(), 8<<10)
	if errors.Is(err, os.ErrNotExist) {
		// A crash before the receipt can leave backup staging only.
		present, err := exists(l.rollbackDir())
		if err != nil || !present {
			return err
		}
		return l.finish()
	}
	if err != nil {
		return err
	}
	var r receipt
	if err := json.Unmarshal(data, &r); err != nil {
		return err
	}
	if r.PreviousVersion != "" {
		if _, err := versionParts(r.PreviousVersion); err != nil {
			return err
		}
	}
	if !r.Committed {
		if err := l.restore(ctx, r, restart); err != nil {
			return err
		}
		// This terminal receipt also makes a failed rollback cleanup retryable.
		r.Committed = true
		if err := l.record(r); err != nil {
			return err
		}
	}
	return l.finish()
}

// Pending reports whether a trial installation has yet to confirm readiness.
func Pending(root string) bool {
	l := layout{root: root}
	data, err := readLocal(l.receiptPath(), 8<<10)
	if errors.Is(err, os.ErrNotExist) {
		return false
	}
	var r receipt
	return err != nil || json.Unmarshal(data, &r) != nil || !r.Committed
}

func (l layout) replace(ctx context.Context, version string, candidate io.Reader) error {
	old, err := l.currentVersion()
	if err != nil {
		return err
	}
	service, err := l.ownsInit()
	if err != nil {
		return err
	}
	haveBinary, err := exists(l.binary())
	if err != nil {
		return err
	}
	if service != (old != "") || haveBinary != (old != "") {
		return errors.New("inconsistent BROray-Light install ownership")
	}
	if old != "" && version != old && !newer(version, old) {
		return errors.New("refusing to downgrade BROray-Light")
	}
	previousRunning := service && l.serviceCmd(ctx, "status") == nil
	if previousRunning {
		if out, err := l.probeReady(ctx, old, false); err != nil {
			return fmt.Errorf("refusing to replace BROray-Light %s: running service is not ready: %w: %s", old, err, strings.TrimSpace(string(out)))
		}
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	dir := l.rollbackDir()
	if err := os.Mkdir(dir, 0o700); err != nil {
		return err
	}
	if err := syncDir(l.root); err != nil {
		return err
	}
	r := receipt{PreviousVersion: old, PreviousRunning: previousRunning}
	if service {
		if err := copyFile(l.binary(), filepath.Join(dir, "binary"), 0o755); err != nil {
			return err
		}
		if err := copyFile(l.service(), filepath.Join(dir, "service"), 0o755); err != nil {
			return err
		}
	}
	if err := l.record(r); err != nil {
		return err
	}

	err = l.activate(ctx, version, candidate, service)
	if err != nil {
		rollbackCtx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
		defer cancel()
		if restoreErr := l.recover(rollbackCtx, true); restoreErr != nil {
			return errors.Join(err, fmt.Errorf("rollback pending: %w", restoreErr))
		}
		return fmt.Errorf("installation rolled back: %w", err)
	}
	r.Committed = true
	if err := l.record(r); err != nil {
		rollbackCtx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
		defer cancel()
		return errors.Join(fmt.Errorf("persist installation confirmation: %w", err), l.recover(rollbackCtx, true))
	}
	return l.finish()
}

func (l layout) activate(ctx context.Context, version string, candidate io.Reader, hadService bool) error {
	if hadService {
		if err := l.serviceCmd(ctx, "stop"); err != nil {
			return err
		}
	}
	if err := atomicFile(l.binary(), 0o755, candidate); err != nil {
		return err
	}
	if err := atomicFile(l.service(), 0o755, bytes.NewReader(l.serviceBody())); err != nil {
		return err
	}
	if err := l.serviceCmd(ctx, "start-installed"); err != nil {
		return err
	}
	if err := l.waitReady(ctx, version, false); err != nil {
		return err
	}
	return atomicFile(l.installed(), 0o600, strings.NewReader(version+"\n"))
}

func (l layout) installLocal(ctx context.Context, source, expected string) error {
	f, err := localFile(source)
	if err != nil {
		return err
	}
	defer f.Close()
	stage, err := os.CreateTemp(l.run, ".local-install-*")
	if err != nil {
		return err
	}
	defer os.Remove(stage.Name())
	defer stage.Close()
	digest := sha256.New()
	n, err := io.Copy(io.MultiWriter(stage, digest), io.LimitReader(f, maxArchive+1))
	if err != nil {
		return err
	}
	if n <= 0 || n > maxArchive || hex.EncodeToString(digest.Sum(nil)) != expected {
		return errors.New("local binary size or SHA-256 mismatch")
	}
	if _, err := stage.Seek(0, io.SeekStart); err != nil {
		return err
	}
	return l.replace(ctx, Version, stage)
}

func (l layout) update(ctx context.Context) error {
	installed, err := l.currentVersion()
	if err != nil {
		return err
	}
	if installed == "" {
		return errors.New("BROray-Light must be installed before updating")
	}
	info, err := Check(ctx)
	if err != nil {
		return err
	}
	if !newer(info.Version, installed) {
		return errors.New("no newer signed BROray-Light version")
	}
	archive, err := os.CreateTemp(l.run, ".update-archive-*")
	if err != nil {
		return err
	}
	defer os.Remove(archive.Name())
	defer archive.Close()
	if err := fetchArchive(ctx, archive, info.Archive); err != nil {
		return err
	}
	if _, err := archive.Seek(0, io.SeekStart); err != nil {
		return err
	}
	candidate, err := os.CreateTemp(l.run, ".update-binary-*")
	if err != nil {
		return err
	}
	defer os.Remove(candidate.Name())
	defer candidate.Close()
	if err := unpackCandidate(archive, candidate, info.Version); err != nil {
		return err
	}
	if _, err := candidate.Seek(0, io.SeekStart); err != nil {
		return err
	}
	return l.replace(ctx, info.Version, candidate)
}

// Launch starts an updater that survives the old daemon stopping itself.
func Launch(ctx context.Context, root, run string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	l := layout{root: root, run: run, init: DefaultInitDir}
	logPath := filepath.Join(l.run, "update.log")
	fd, err := unix.Open(logPath, unix.O_WRONLY|unix.O_APPEND|unix.O_CREAT|unix.O_NOFOLLOW|unix.O_CLOEXEC|unix.O_NONBLOCK, 0o600)
	if err != nil {
		return err
	}
	log := os.NewFile(uintptr(fd), logPath)
	defer log.Close()
	st, err := log.Stat()
	if err != nil {
		return err
	}
	if !st.Mode().IsRegular() || st.Mode().Perm() != 0o600 || st.Sys().(*syscall.Stat_t).Uid != uint32(os.Geteuid()) {
		return errors.New("invalid updater log file")
	}
	cmd := exec.Command(l.binary(), "update", "--root", l.root, "--run", l.run)
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	cmd.Stdout, cmd.Stderr = log, log
	if err := cmd.Start(); err != nil {
		return err
	}
	go func() { _ = cmd.Wait() }()
	return nil
}
