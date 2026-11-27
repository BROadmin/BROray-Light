package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/BROadmin/broray-light/internal/lightapp"
	"github.com/BROadmin/broray-light/internal/lightinstall"
	"github.com/BROadmin/broray-light/internal/lightkeenetic"
	"github.com/BROadmin/broray-light/internal/lightruntime"
	"github.com/BROadmin/broray-light/web/light"
	"golang.org/x/sys/unix"
)

const defaultRoot = "/opt/broray-light"
const defaultRun = "/tmp/broray-light/run"

func main() {
	if err := run(os.Args[1:]); err != nil {
		log.Print(err)
		os.Exit(1)
	}
}

func run(args []string) error {
	if len(args) == 0 {
		return errors.New("usage: broray-light serve|ready|version|install|update|recover")
	}
	switch args[0] {
	case "version", "--version":
		fmt.Println("BROray-Light " + lightapp.Version)
		return nil
	case "install", "update", "recover":
		return lightinstall.Run(args)
	case "serve", "ready":
		return daemonCommand(args)
	default:
		return errors.New("unknown BROray-Light command")
	}
}

func daemonCommand(args []string) error {
	flags := flag.NewFlagSet(args[0], flag.ContinueOnError)
	root := flags.String("root", defaultRoot, "Light installation directory")
	runtimeDir := flags.String("run", defaultRun, "Light private runtime directory")
	if args[0] == "ready" {
		expected := flags.String("version", "", "required running version")
		serviceOnly := flags.Bool("service-only", false, "confirm restored service identity independently of proxy readiness")
		if err := flags.Parse(args[1:]); err != nil {
			return err
		}
		if *serviceOnly && *expected == "" {
			return errors.New("service identity requires an expected version")
		}
		return ready(filepath.Clean(*root), filepath.Clean(*runtimeDir), *expected, *serviceOnly)
	}
	listen := flags.String("listen", "", "WebUI address (default router LAN on port 8080)")
	socks := flags.String("socks", "127.0.0.1:1089", "local Xray SOCKS address")
	probe := flags.String("probe-url", "https://connectivitycheck.gstatic.com/generate_204", "HTTPS connectivity check")
	if err := flags.Parse(args[1:]); err != nil {
		return err
	}
	sockHost, _, err := net.SplitHostPort(*socks)
	if err != nil || net.ParseIP(sockHost) == nil || !net.ParseIP(sockHost).IsLoopback() {
		return errors.New("SOCKS must bind a loopback IP")
	}
	u, err := url.Parse(*probe)
	if err != nil || u.Hostname() == "" || (u.Scheme != "https" && (u.Scheme != "http" || net.ParseIP(u.Hostname()) == nil || !net.ParseIP(u.Hostname()).IsLoopback())) {
		return errors.New("probe URL must use HTTPS or HTTP on loopback")
	}
	return serve(filepath.Clean(*root), filepath.Clean(*runtimeDir), *listen, *socks, *probe)
}

func secureDirectory(path string) error {
	if err := os.MkdirAll(path, 0700); err != nil {
		return err
	}
	info, err := os.Lstat(path)
	if err != nil {
		return err
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !info.IsDir() || !ok || stat.Uid != uint32(os.Geteuid()) || info.Mode().Perm()&0022 != 0 {
		return fmt.Errorf("unsafe Light directory: %s", path)
	}
	return nil
}

func serve(root, run, listen, socks, probe string) error {
	if !filepath.IsAbs(root) || !filepath.IsAbs(run) || root == run {
		return errors.New("root and runtime must be distinct absolute paths")
	}
	if err := lightapp.NoFullProduct(root); err != nil {
		return err
	}
	for _, dir := range []string{root, filepath.Join(root, "state"), filepath.Dir(run), run} {
		if err := secureDirectory(dir); err != nil {
			return err
		}
	}
	fd, err := unix.Open(filepath.Join(run, "daemon.lock"), unix.O_CREAT|unix.O_CLOEXEC|unix.O_NOFOLLOW|unix.O_RDWR, 0600)
	if err != nil {
		return err
	}
	defer unix.Close(fd)
	if err := unix.Flock(fd, unix.LOCK_EX|unix.LOCK_NB); err != nil {
		return errors.New("another Light daemon owns this runtime")
	}
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()

	router := lightkeenetic.New(filepath.Join(root, "state"))
	if listen == "" {
		for {
			addr, err := router.LANIPv4(ctx)
			if err == nil {
				listen = net.JoinHostPort(addr.String(), "8080")
				break
			}
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(3 * time.Second):
			}
		}
	}
	xray := lightruntime.New(filepath.Join(root, "runtime", "xray", "xray"), run, socks, probe)
	if err := xray.RecoverCore(); err != nil {
		return err
	}
	app, err := lightapp.New(root, run, socks, xray, router)
	if err != nil {
		return err
	}
	defer app.Close()
	public, err := net.Listen("tcp", listen)
	if err != nil {
		return err
	}
	defer public.Close()

	controlPath := filepath.Join(run, "control.sock")
	if old, err := os.Lstat(controlPath); err == nil {
		if old.Mode()&os.ModeSocket == 0 {
			return errors.New("unexpected object at Light control socket path")
		}
		if err := os.Remove(controlPath); err != nil {
			return err
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return err
	}
	control, err := net.Listen("unix", controlPath)
	if err != nil {
		return err
	}
	defer control.Close()
	if err := os.Chmod(controlPath, 0600); err != nil {
		return err
	}

	var publicHTTP = &http.Server{Handler: app.Handler(light.Assets), ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 20 * time.Second, IdleTimeout: 20 * time.Second, MaxHeaderBytes: 16 << 10}
	var controlHTTP = &http.Server{Handler: app.ControlHandler(), ReadHeaderTimeout: 3 * time.Second, IdleTimeout: 5 * time.Second, MaxHeaderBytes: 4 << 10}
	failures := make(chan error, 2)
	go func() { failures <- publicHTTP.Serve(public) }()
	go func() { failures <- controlHTTP.Serve(control) }()
	watchDone := make(chan struct{})
	go func() { defer close(watchDone); app.Watch(ctx) }()
	webDone := make(chan struct{})
	go func() { defer close(webDone); app.RunRemoteAccess(ctx, public.Addr().String()) }()
	log.Printf("BROray-Light %s listening on %s", lightapp.Version, public.Addr())
	select {
	case err = <-failures:
	case <-ctx.Done():
	}
	cancel()
	_ = controlHTTP.Close()
	_ = publicHTTP.Close()
	<-watchDone
	<-webDone
	return err
}

func ready(root, run, expected string, serviceOnly bool) error {
	path := filepath.Join(run, "control.sock")
	transport := &http.Transport{DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
		return (&net.Dialer{}).DialContext(ctx, "unix", path)
	}}
	defer transport.CloseIdleConnections()
	client := &http.Client{Transport: transport, Timeout: 16 * time.Second}
	endpoint := "/ready"
	if serviceOnly {
		endpoint = "/identity"
	}
	response, err := client.Get("http://light" + endpoint + "?version=" + url.QueryEscape(expected) + "&root=" + url.QueryEscape(root))
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		data, _ := io.ReadAll(io.LimitReader(response.Body, 1024))
		return fmt.Errorf("Light readiness failed: %s", data)
	}
	return nil
}
