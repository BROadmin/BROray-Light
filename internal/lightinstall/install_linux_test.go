package lightinstall

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"testing"
	"time"
)

// The packaged init script needs a real executable to verify /proc/PID/exe.
// Re-execute the test binary as a tiny foreground daemon and readiness probe.
func TestMain(m *testing.M) {
	if os.Getenv("BRORAY_LIGHT_INSTALL_FIXTURE") == "1" && len(os.Args) >= 2 {
		switch os.Args[1] {
		case "serve":
			wait, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM)
			defer stop()
			<-wait.Done()
			os.Exit(0)
		case "ready":
			if err := fixtureReady(os.Args[2:]); err != nil {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(1)
			}
			os.Exit(0)
		case "recover":
			if err := Run(os.Args[1:]); err != nil {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(1)
			}
			os.Exit(0)
		}
	}
	os.Exit(m.Run())
}

func fixtureReady(args []string) error {
	serviceOnly := len(args) > 0 && args[len(args)-1] == "--service-only"
	if serviceOnly && os.Getenv("BRORAY_LIGHT_INSTALL_LEGACY_READY") == "1" {
		return fmt.Errorf("flag provided but not defined: -service-only")
	}
	flags := make(map[string]string)
	for i := 0; i+1 < len(args); i += 2 {
		flags[args[i]] = args[i+1]
	}
	version := flags["--version"]
	if version == "" {
		return fmt.Errorf("readiness probe omitted expected version")
	}
	pid, err := os.ReadFile(filepath.Join(flags["--run"], "daemon.pid"))
	if err != nil {
		return err
	}
	exe, err := os.Readlink(filepath.Join("/proc", strings.TrimSpace(string(pid)), "exe"))
	if err != nil || exe != filepath.Join(flags["--root"], "bin", BinaryName) {
		return fmt.Errorf("service process is not running")
	}
	l := layout{root: flags["--root"]}
	if serviceOnly {
		installed, err := l.currentVersion()
		if err != nil || installed != version || !Pending(l.root) {
			return fmt.Errorf("service-only readiness must check a restored installation awaiting confirmation")
		}
		return nil
	}
	if version == os.Getenv("BRORAY_LIGHT_INSTALL_HEALTH_FAIL") ||
		(Pending(l.root) && os.Getenv("BRORAY_LIGHT_INSTALL_HEALTH_FAIL_PENDING") == "1") {
		return fmt.Errorf("active connection remains unavailable")
	}
	if !Pending(l.root) {
		installed, err := l.currentVersion()
		if err != nil || installed != version {
			return fmt.Errorf("readiness probe targets an unexpected installed version")
		}
	}
	return nil
}

func testLayout(t *testing.T) layout {
	t.Helper()
	base := t.TempDir()
	l := layout{root: filepath.Join(base, "opt", "broray-light"), run: filepath.Join(base, "tmp", "broray-light", "run"),
		init: filepath.Join(base, "opt", "etc", "init.d")}
	if err := l.prepare(); err != nil {
		t.Fatal(err)
	}
	return l
}

func TestInstallConflictGuards(t *testing.T) {
	for _, tc := range []struct {
		name string
		path func(layout) string
	}{
		{"full BROray", func(l layout) string { return filepath.Join(filepath.Dir(l.root), "broray") }},
		{"legacy Light", func(l layout) string { return filepath.Join(l.root, "bin", "broray-lightd") }},
		{"foreign init", func(l layout) string { return l.service() }},
	} {
		t.Run(tc.name, func(t *testing.T) {
			l := testLayout(t)
			if err := os.WriteFile(tc.path(l), []byte("untouched"), 0o755); err != nil {
				t.Fatal(err)
			}
			if err := l.prepare(); err == nil {
				t.Fatal("accepted a conflicting installation")
			}
			b, err := os.ReadFile(tc.path(l))
			if err != nil || string(b) != "untouched" {
				t.Fatalf("modified conflicting path: %q, %v", b, err)
			}
		})
	}
}

func TestRollbackOnUnreadyCandidate(t *testing.T) {
	testRollbackOnUnreadyCandidate(t, false)
}

func TestRollbackConfirmsRestoredServiceDuringConnectivityOutage(t *testing.T) {
	testRollbackOnUnreadyCandidate(t, true)
}

func testRollbackOnUnreadyCandidate(t *testing.T, outage bool) {
	t.Helper()
	l := testLayout(t)
	t.Setenv("BRORAY_LIGHT_INSTALL_FIXTURE", "1")
	t.Setenv("BRORAY_LIGHT_INSTALL_HEALTH_FAIL", "3.5.11")
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	binary, err := os.ReadFile(exe)
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 12*time.Second)
	defer cancel()
	if err := l.replace(ctx, Version, bytes.NewReader(binary)); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = l.serviceCmd(context.Background(), "stop") })
	if Pending(l.root) {
		t.Fatal("ready install is still pending")
	}
	if outage {
		t.Setenv("BRORAY_LIGHT_INSTALL_HEALTH_FAIL_PENDING", "1")
	} else {
		t.Setenv("BRORAY_LIGHT_INSTALL_LEGACY_READY", "1")
	}
	candidate := append(append([]byte(nil), binary...), 'T')
	updateCtx, stopUpdate := context.WithTimeout(context.Background(), 3500*time.Millisecond)
	defer stopUpdate()
	if err := l.replace(updateCtx, "3.5.11", bytes.NewReader(candidate)); err == nil ||
		!strings.Contains(err.Error(), "installation rolled back") {
		t.Fatalf("expected confirmed rollback, got %v", err)
	}
	installed, err := l.currentVersion()
	if err != nil || installed != Version || Pending(l.root) {
		t.Fatalf("rollback left current version/receipt %q, pending=%t, %v", installed, Pending(l.root), err)
	}
	b, err := os.ReadFile(l.binary())
	if err != nil || !bytes.Equal(b, binary) {
		t.Fatalf("prior binary was not restored: %v", err)
	}
	if err := l.serviceCmd(ctx, "status"); err != nil {
		t.Fatalf("prior daemon was not restarted: %v", err)
	}
}

func TestReplaceRefusesUnreadyRunningInstallation(t *testing.T) {
	l := testLayout(t)
	t.Setenv("BRORAY_LIGHT_INSTALL_FIXTURE", "1")
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	binary, err := os.ReadFile(exe)
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 12*time.Second)
	defer cancel()
	if err := l.replace(ctx, Version, bytes.NewReader(binary)); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = l.serviceCmd(context.Background(), "stop") })
	pidfile := filepath.Join(l.run, "daemon.pid")
	previousPID, err := os.ReadFile(pidfile)
	if err != nil {
		t.Fatal(err)
	}
	t.Setenv("BRORAY_LIGHT_INSTALL_HEALTH_FAIL", Version)
	updateErr := l.replace(ctx, "3.5.11", bytes.NewReader(binary))
	if updateErr == nil || !strings.Contains(updateErr.Error(), "active connection remains unavailable") {
		t.Errorf("expected refusal due to existing service readiness, got %v", updateErr)
	}
	if installed, err := l.currentVersion(); err != nil || installed != Version {
		t.Errorf("installed version changed: %q, %v", installed, err)
	}
	if pid, err := os.ReadFile(pidfile); err != nil || !bytes.Equal(pid, previousPID) {
		t.Errorf("prior daemon PID changed: %q, %v", pid, err)
	}
	if err := l.serviceCmd(ctx, "status"); err != nil {
		t.Errorf("prior daemon is not running: %v", err)
	}
	for _, path := range []string{l.receiptPath(), l.rollbackDir()} {
		if present, err := exists(path); err != nil || present {
			t.Errorf("upgrade created transaction state at %s: %t, %v", path, present, err)
		}
	}
}

func TestCleanupFailurePreservesReceipt(t *testing.T) {
	l := testLayout(t)
	if err := os.Mkdir(l.rollbackDir(), 0o700); err != nil {
		t.Fatal(err)
	}
	foreign := filepath.Join(l.rollbackDir(), "foreign")
	if err := os.Mkdir(foreign, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := l.record(receipt{PreviousVersion: Version, Committed: true}); err != nil {
		t.Fatal(err)
	}
	if err := l.recover(context.Background(), true); err == nil {
		t.Fatal("cleanup unexpectedly removed a foreign object")
	}
	if _, err := os.Stat(l.receiptPath()); err != nil {
		t.Fatalf("cleanup lost the recovery receipt: %v", err)
	}
	if err := os.Remove(foreign); err != nil {
		t.Fatal(err)
	}
	if err := l.recover(context.Background(), true); err != nil {
		t.Fatalf("could not retry cleanup: %v", err)
	}
	if yes, err := exists(l.receiptPath()); err != nil || yes {
		t.Fatalf("completed cleanup left a receipt: %t, %v", yes, err)
	}
}

func TestInitRecoversUnconfirmedCandidate(t *testing.T) {
	l := testLayout(t)
	t.Setenv("BRORAY_LIGHT_INSTALL_FIXTURE", "1")
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	binary, err := os.ReadFile(exe)
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	if err := l.replace(ctx, Version, bytes.NewReader(binary)); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = l.serviceCmd(context.Background(), "stop") })
	if err := l.serviceCmd(ctx, "stop"); err != nil {
		t.Fatal(err)
	}
	dir := l.rollbackDir()
	if err := os.Mkdir(dir, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := copyFile(l.binary(), filepath.Join(dir, "binary"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := copyFile(l.service(), filepath.Join(dir, "service"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := l.record(receipt{PreviousVersion: Version, PreviousRunning: true}); err != nil {
		t.Fatal(err)
	}
	if err := atomicFile(l.binary(), 0o755, strings.NewReader("#!/bin/sh\nexit 1\n")); err != nil {
		t.Fatal(err)
	}
	if err := l.serviceCmd(ctx, "start"); err != nil {
		t.Fatalf("init did not recover the previous executable: %v", err)
	}
	if Pending(l.root) {
		t.Fatal("interrupted update still pending after startup")
	}
	b, err := os.ReadFile(l.binary())
	if err != nil || !bytes.Equal(b, binary) {
		t.Fatalf("init failed to restore the executable: %v", err)
	}
}
