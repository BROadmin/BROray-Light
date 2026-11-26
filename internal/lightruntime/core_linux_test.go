package lightruntime

import (
	"os"
	"path/filepath"
	"testing"
)

func TestCoreInterruptedSwapRestoresPreviousBytes(t *testing.T) {
	dir := t.TempDir()
	binary := filepath.Join(dir, "xray")
	previous := binary + ".previous"
	if err := os.WriteFile(previous, []byte("old-core"), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(binary, []byte("new-core"), 0700); err != nil {
		t.Fatal(err)
	}
	rt := New(binary, dir, "", "")
	if err := rt.recordCore(coreTransaction{Previous: true}); err != nil {
		t.Fatal(err)
	}
	if err := rt.RecoverCore(); err != nil {
		t.Fatal(err)
	}
	got, err := os.ReadFile(binary)
	if err != nil || string(got) != "old-core" {
		t.Fatalf("rollback lost prior core: %q %v", got, err)
	}
	if err := rt.RecoverCore(); err != nil {
		t.Fatalf("second recovery: %v", err)
	}
}

func TestCoreUnfinishedCleanupRetainsReceipt(t *testing.T) {
	dir := t.TempDir()
	binary := filepath.Join(dir, "xray")
	previous := binary + ".previous"
	if err := os.Mkdir(previous, 0700); err != nil {
		t.Fatal(err)
	}
	blocker := filepath.Join(previous, "unexpected")
	if err := os.WriteFile(blocker, []byte("retain"), 0600); err != nil {
		t.Fatal(err)
	}
	rt := New(binary, dir, "", "")
	if err := rt.recordCore(coreTransaction{Previous: true, Committed: true}); err != nil {
		t.Fatal(err)
	}
	if err := rt.RecoverCore(); err == nil {
		t.Fatal("cleanup unexpectedly claimed success")
	}
	if _, err := os.Stat(binary + ".transaction"); err != nil {
		t.Fatalf("cleanup discarded transaction: %v", err)
	}
	if _, err := os.Stat(blocker); err != nil {
		t.Fatalf("unexpected data was modified: %v", err)
	}
	if err := os.Remove(blocker); err != nil {
		t.Fatal(err)
	}
	if err := rt.RecoverCore(); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(binary + ".transaction"); !os.IsNotExist(err) {
		t.Fatalf("completed receipt remained: %v", err)
	}
}
