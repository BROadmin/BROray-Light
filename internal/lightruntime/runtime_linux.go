package lightruntime

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"syscall"
	"time"

	"github.com/BROadmin/broray-light/modules/servers"
)

type Runtime struct {
	binary   string
	run      string
	address  string
	probeURL string
	active   *child
}

type child struct {
	cmd  *exec.Cmd
	done chan struct{}
}

func New(binary, run, address, probeURL string) *Runtime {
	return &Runtime{binary: binary, run: run, address: address, probeURL: probeURL}
}

func (r *Runtime) Running() bool { return r.active != nil && r.active.running() }

func (p *child) running() bool {
	select {
	case <-p.done:
		return false
	default:
		return true
	}
}

func (r *Runtime) command(ctx context.Context, args ...string) *exec.Cmd {
	cmd := exec.CommandContext(ctx, r.binary, args...)
	cmd.Env = append(os.Environ(), "XRAY_LOCATION_ASSET="+filepath.Dir(r.binary))
	return cmd
}

func (r *Runtime) configuration(profile servers.Server, address string) (string, error) {
	host, portText, err := net.SplitHostPort(address)
	if err != nil {
		return "", err
	}
	port, err := strconv.Atoi(portText)
	if err != nil {
		return "", err
	}
	if servers.Outbound(profile) == nil {
		return "", errors.New("unsupported Xray profile")
	}
	data, err := json.Marshal(servers.XrayConfig(profile, host, port, "warning", "none", "none"))
	if err != nil {
		return "", err
	}
	f, err := os.CreateTemp(r.run, "xray-*.json")
	if err != nil {
		return "", err
	}
	name := f.Name()
	_, writeErr := f.Write(data)
	closeErr := f.Close()
	if err := errors.Join(writeErr, closeErr); err != nil {
		os.Remove(name)
		return "", err
	}
	return name, nil
}

func (r *Runtime) spawn(ctx context.Context, profile servers.Server, address string) (*child, error) {
	path, err := r.configuration(profile, address)
	if err != nil {
		return nil, err
	}
	// Xray must finish reading this configuration before its temporary file is removed.
	listener, err := net.Listen("tcp", address)
	if err != nil {
		os.Remove(path)
		return nil, errors.New("SOCKS address is already in use")
	}
	listener.Close()
	validation, cancel := context.WithTimeout(ctx, 10*time.Second)
	err = r.command(validation, "run", "-test", "-config", path).Run()
	cancel()
	if err != nil {
		os.Remove(path)
		return nil, fmt.Errorf("Xray config validation failed: %w", err)
	}

	// As in the pinned donor, the Linux parent-death signal is associated
	// with the creating OS thread. Keep that thread alive until Wait returns.
	started := make(chan error, 1)
	cmd := r.command(context.Background(), "run", "-config", path)
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true, Pdeathsig: syscall.SIGKILL}
	proc := &child{cmd: cmd, done: make(chan struct{})}
	go func() {
		runtime.LockOSThread()
		defer runtime.UnlockOSThread()
		defer close(proc.done)
		defer os.Remove(path)
		err := cmd.Start()
		started <- err
		if err == nil {
			_ = cmd.Wait()
		}
	}()
	if err := <-started; err != nil {
		return nil, err
	}
	attempt, cancel := context.WithTimeout(ctx, 12*time.Second)
	defer cancel()
	ticker := time.NewTicker(120 * time.Millisecond)
	defer ticker.Stop()
	for {
		select {
		case <-attempt.Done():
			return nil, errors.Join(attempt.Err(), proc.stop())
		case <-proc.done:
			return nil, errors.New("Xray exited during startup")
		case <-ticker.C:
			conn, err := (&net.Dialer{Timeout: 150 * time.Millisecond}).DialContext(attempt, "tcp", address)
			if err == nil {
				conn.Close()
				if proc.running() {
					return proc, nil
				}
			}
		}
	}
}

func (p *child) stop() error {
	if !p.running() {
		return nil
	}
	err := syscall.Kill(-p.cmd.Process.Pid, syscall.SIGTERM)
	if err != nil && err != syscall.ESRCH {
		return err
	}
	timer := time.NewTimer(2 * time.Second)
	defer timer.Stop()
	select {
	case <-p.done:
		return nil
	case <-timer.C:
	}
	err = syscall.Kill(-p.cmd.Process.Pid, syscall.SIGKILL)
	if err != nil && err != syscall.ESRCH {
		return err
	}
	timer.Reset(3 * time.Second)
	select {
	case <-p.done:
		return nil
	case <-timer.C:
		return errors.New("owned Xray process has not exited")
	}
}

func (r *Runtime) Stop() error {
	if r.active == nil {
		return nil
	}
	if err := r.active.stop(); err != nil {
		return err
	}
	r.active = nil
	return nil
}

func (r *Runtime) Start(ctx context.Context, profile servers.Server) error {
	if err := r.Stop(); err != nil {
		return err
	}
	proc, err := r.spawn(ctx, profile, r.address)
	if err == nil {
		r.active = proc
	}
	return err
}

func (r *Runtime) Check(ctx context.Context, profile servers.Server) error {
	leaf, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		return err
	}
	address := leaf.Addr().String()
	leaf.Close()
	proc, err := r.spawn(ctx, profile, address)
	if err != nil {
		return err
	}
	return errors.Join(r.probe(ctx, proc, address), proc.stop())
}

func (r *Runtime) Probe(ctx context.Context) error {
	return r.probe(ctx, r.active, r.address)
}

func (r *Runtime) probe(ctx context.Context, proc *child, address string) error {
	if proc == nil || !proc.running() {
		return errors.New("Xray is stopped")
	}
	proxy := &url.URL{Scheme: "socks5h", Host: address}
	transport := &http.Transport{Proxy: http.ProxyURL(proxy), TLSHandshakeTimeout: 5 * time.Second, DisableKeepAlives: true}
	defer transport.CloseIdleConnections()
	client := &http.Client{
		Transport: transport, Timeout: 8 * time.Second,
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, r.probeURL, nil)
	if err != nil {
		return err
	}
	response, err := client.Do(req)
	if err != nil {
		return errors.New("probe through Xray failed")
	}
	defer response.Body.Close()
	_, err = io.Copy(io.Discard, io.LimitReader(response.Body, 512))
	if err != nil || response.StatusCode < 200 || response.StatusCode >= 300 || !proc.running() {
		return errors.New("probe through Xray did not confirm connectivity")
	}
	return nil
}
