package lightruntime

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/BROadmin/broray-light/modules/servers"
)

func fixture(t *testing.T) (string, string, string) {
	t.Helper()
	dir := t.TempDir()
	binary := filepath.Join(dir, "xray")
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	script := "#!/bin/sh\nif [ \"$2\" = -test ]; then test -s \"$4\"; exit; fi\nexec " + strconv.Quote(exe) + " -test.run=^TestSOCKSFixture$ -- \"$@\"\n"
	if err := os.WriteFile(binary, []byte(script), 0700); err != nil {
		t.Fatal(err)
	}
	tcp, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	address := tcp.Addr().String()
	tcp.Close()
	return dir, binary, address
}

func sample() servers.Server {
	return servers.Server{ID: "fixture", Name: "fixture", Protocol: "vless", Network: "raw", Security: "none", Address: "fixture.example", Port: 443, UUID: "11111111-1111-4111-8111-111111111111"}
}

func TestSOCKSFixture(t *testing.T) {
	if os.Getenv("LIGHT_XRAY_FIXTURE") != "1" || len(os.Args) < 4 {
		return
	}
	data, err := os.ReadFile(os.Args[len(os.Args)-1])
	if err != nil {
		t.Fatal(err)
	}
	var config struct {
		Inbounds []struct {
			Listen string
			Port   int
		}
	}
	if err := json.Unmarshal(data, &config); err != nil || len(config.Inbounds) != 1 {
		t.Fatalf("invalid fixture configuration: %v", err)
	}
	in := config.Inbounds[0]
	socket, err := net.Listen("tcp", net.JoinHostPort(in.Listen, strconv.Itoa(in.Port)))
	if err != nil {
		t.Fatal(err)
	}
	defer socket.Close()
	for {
		conn, err := socket.Accept()
		if err != nil {
			return
		}
		go fixtureProxy(conn)
	}
}

func fixtureProxy(conn net.Conn) {
	defer conn.Close()
	_ = conn.SetDeadline(time.Now().Add(5 * time.Second))
	header := make([]byte, 4)
	if _, err := io.ReadFull(conn, header[:2]); err != nil || header[0] != 5 {
		return
	}
	if _, err := io.CopyN(io.Discard, conn, int64(header[1])); err != nil {
		return
	}
	if _, err := conn.Write([]byte{5, 0}); err != nil {
		return
	}
	if _, err := io.ReadFull(conn, header); err != nil || header[0] != 5 || header[1] != 1 || header[3] != 1 {
		return
	}
	target := make([]byte, 6)
	if _, err := io.ReadFull(conn, target); err != nil {
		return
	}
	if !net.IP(target[:4]).IsLoopback() {
		return
	}
	upstream, err := net.DialTimeout("tcp4", net.JoinHostPort(net.IP(target[:4]).String(), strconv.Itoa(int(binary.BigEndian.Uint16(target[4:])))), time.Second)
	if err != nil {
		return
	}
	defer upstream.Close()
	if _, err := conn.Write([]byte{5, 0, 0, 1, 127, 0, 0, 1, 0, 0}); err != nil {
		return
	}
	go io.Copy(upstream, conn)
	_, _ = io.Copy(conn, upstream)
}

func TestProbeUsesSOCKSAndRequiresHTTPResponse(t *testing.T) {
	t.Setenv("LIGHT_XRAY_FIXTURE", "1")
	dir, binary, address := fixture(t)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/ready" {
			http.NotFound(w, r)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()
	r := New(binary, dir, address, server.URL+"/ready")
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	if err := r.Start(ctx, sample()); err != nil {
		t.Fatal(err)
	}
	defer r.Stop()
	if err := r.Probe(ctx); err != nil {
		t.Fatal(err)
	}
	r.probeURL = server.URL + "/wrong"
	if err := r.Probe(ctx); err == nil {
		t.Fatal("a listener and unrelated response satisfied readiness")
	}
}

func TestParentFixture(t *testing.T) {
	if os.Getenv("LIGHT_PARENT_FIXTURE") != "1" {
		return
	}
	dir := os.Getenv("LIGHT_FIXTURE_DIR")
	r := New(filepath.Join(dir, "xray"), dir, os.Getenv("LIGHT_FIXTURE_ADDR"), "")
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	if err := r.Start(ctx, sample()); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "pid"), []byte(strconv.Itoa(r.active.cmd.Process.Pid)), 0600); err != nil {
		t.Fatal(err)
	}
	// Killed by TestOwnedXrayDiesWithDaemon. keep timers active under go test.
	time.Sleep(time.Minute)
}

func TestOwnedXrayDiesWithDaemon(t *testing.T) {
	dir, _, address := fixture(t)
	var stdout strings.Builder
	cmd := exec.Command(os.Args[0], "-test.run=^TestParentFixture$")
	cmd.Stdout, cmd.Stderr = &stdout, &stdout
	cmd.Env = append(os.Environ(), "LIGHT_PARENT_FIXTURE=1", "LIGHT_XRAY_FIXTURE=1", "LIGHT_FIXTURE_DIR="+dir, "LIGHT_FIXTURE_ADDR="+address)
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	defer func() { _ = cmd.Process.Kill(); _ = cmd.Wait() }()
	until := time.Now().Add(20 * time.Second)
	var pid int
	for pid == 0 && time.Now().Before(until) {
		body, _ := os.ReadFile(filepath.Join(dir, "pid"))
		pid, _ = strconv.Atoi(string(body))
		time.Sleep(50 * time.Millisecond)
	}
	if pid == 0 {
		_ = cmd.Process.Kill()
		_ = cmd.Wait()
		t.Fatalf("child did not start: %s", &stdout)
	}
	if err := cmd.Process.Kill(); err != nil {
		t.Fatal(err)
	}
	_ = cmd.Wait()
	until = time.Now().Add(8 * time.Second)
	for time.Now().Before(until) {
		data, err := os.ReadFile(fmt.Sprintf("/proc/%d/stat", pid))
		if os.IsNotExist(err) || strings.Contains(string(data), ") Z ") {
			return
		}
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatalf("Xray process %d outlived a SIGKILL-ed daemon", pid)
}
