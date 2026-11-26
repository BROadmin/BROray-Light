package lightkeenetic

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"
)

const testSOCKS = "127.0.0.1:2081"
const otherSOCKS = "127.0.0.1:2082"
const routerBase = "! $$$ Model: fixture\nsystem\n    hostname test\n!\ninterface Bridge0\n    ip address 192.168.1.1 255.255.255.0\n!\n"
const foreignProxy = "interface Proxy0\n    description Other\n    proxy protocol socks5\n    proxy upstream 192.168.1.10 2080\n    up\n!\n"

type fakeRouter struct {
	running, startup                string
	desc, upstream                  string
	name                            string
	writes                          []string
	failSave, on, refuseDescription bool
}

func (r *fakeRouter) run(_ context.Context, command string) (string, error) {
	switch command {
	case "show running-config":
		return r.running, nil
	case "more startup-config":
		return r.startup, nil
	case "show interface Bridge0":
		return "type: Bridge\naddress: 192.168.1.1\n", nil
	case "show interface " + r.name:
		connected := "yes"
		if !r.on {
			connected = "no"
		}
		return "type: Proxy\nlink: up\nstate: up\nconnected: " + connected + "\ndescription: " + r.desc + "\n", nil
	}
	r.writes = append(r.writes, command)
	if command == "system configuration save" {
		if r.failSave {
			return "", errors.New("simulated saving error")
		}
		r.startup = r.running
		return "", nil
	}
	if command == "no interface "+r.name {
		r.running = routerBase + foreignProxy
		return "", nil
	}
	words := strings.SplitN(command, " ", 3)
	if len(words) < 2 || words[0] != "interface" || words[1] == "Proxy0" {
		return "", errors.New("unexpected command: " + command)
	}
	r.name = words[1]
	if len(words) == 2 {
		return "", nil
	}
	value := words[2]
	if desc, ok := strings.CutPrefix(value, "description "); ok {
		if r.refuseDescription {
			return "error: description", nil
		}
		r.desc = desc
	}
	if upstream, ok := strings.CutPrefix(value, "proxy upstream "); ok {
		r.upstream = upstream
	}
	if value == "up" || strings.HasPrefix(value, "proxy upstream ") && r.startup != routerBase+foreignProxy {
		r.running = routerBase + foreignProxy + "interface " + r.name + "\n    description " + r.desc +
			"\n    security-level public\n    ip global 4100\n    proxy protocol socks5\n    proxy upstream " + r.upstream +
			"\n    proxy connect via ISP\n    up\n!\n"
	}
	return "", nil
}

func fixture(t *testing.T) (*Client, *fakeRouter) {
	t.Helper()
	client := New(t.TempDir())
	router := &fakeRouter{running: routerBase + foreignProxy, startup: routerBase + foreignProxy, on: true}
	client.run, client.settle = router.run, 0
	return client, router
}

func TestCreateUsesFreeNameAndRetainsIdentityWhenEndpointChanges(t *testing.T) {
	c, router := fixture(t)
	ctx := context.Background()
	if err := c.Ensure(ctx, testSOCKS); err != nil {
		t.Fatal(err)
	}
	receipt, err := c.load()
	if err != nil || receipt == nil || receipt.Name != "Proxy1" || receipt.Phase != managed {
		t.Fatalf("receipt = %#v, %v", receipt, err)
	}
	if err := c.Ready(ctx, testSOCKS); err != nil {
		t.Fatal(err)
	}
	router.on = false
	if err := c.Ready(ctx, testSOCKS); !errors.Is(err, ErrNotReady) {
		t.Fatalf("disconnected interface passed: %v", err)
	}
	router.on = true
	router.writes = nil
	if err := c.Ensure(ctx, otherSOCKS); err != nil {
		t.Fatal(err)
	}
	if err := c.Ready(ctx, otherSOCKS); err != nil {
		t.Fatal(err)
	}
	after, err := c.load()
	if err != nil || receipt.Description != after.Description || receipt.Name != after.Name {
		t.Fatalf("changed ownership: %#v, %v", after, err)
	}
	if !slices.Equal(router.writes, []string{"interface Proxy1 proxy upstream 127.0.0.1 2082", "interface Proxy1 proxy connect", "system configuration save"}) {
		t.Fatalf("unexpected writes: %v", router.writes)
	}
	if !strings.Contains(router.running, foreignProxy) || !strings.Contains(router.startup, foreignProxy) {
		t.Fatal("foreign proxy changed")
	}
}

func TestCleanupRetainsProofOnSaveFailureAndRetriesWithoutReissuingDelete(t *testing.T) {
	c, router := fixture(t)
	ctx := context.Background()
	if err := c.Ensure(ctx, testSOCKS); err != nil {
		t.Fatal(err)
	}
	router.failSave = true
	if err := c.Cleanup(ctx); err == nil {
		t.Fatal("cleanup ignored save failure")
	}
	got, err := c.load()
	if err != nil || got == nil || got.Phase != cleaning {
		t.Fatalf("lost cleanup proof: %#v, %v", got, err)
	}
	router.failSave = false
	router.writes = nil
	if err := c.Cleanup(ctx); err != nil {
		t.Fatal(err)
	}
	if !slices.Equal(router.writes, []string{"system configuration save"}) ||
		router.running != routerBase+foreignProxy || router.startup != router.running {
		t.Fatalf("wrong retry: %v", router.writes)
	}
	if _, err := os.Stat(filepath.Join(c.stateDir, receiptFile)); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("cleanup did not remove receipt: %v", err)
	}
}

func TestRefusesForeignInterfaceChangeRouteReferenceAndUnsavedEdits(t *testing.T) {
	for _, test := range []struct {
		name   string
		modify func(*fakeRouter)
		want   error
	}{
		{"additional binding", func(r *fakeRouter) {
			r.running = strings.Replace(r.running, "    proxy connect via ISP\n", "    proxy connect via ISP\n    proxy connect via ISP2\n", 1)
		}, ErrOwnership},
		{"external route", func(r *fakeRouter) {
			r.running += "ip route 192.0.2.0/24 Proxy1\n"
			r.startup = r.running
		}, ErrOwnership},
		{"unsaved change", func(r *fakeRouter) {
			r.running = strings.Replace(r.running, "hostname test", "hostname edited", 1)
		}, errUnsaved},
		{"replaced description", func(r *fakeRouter) {
			r.running = strings.Replace(r.running, r.desc, "Foreign", 1)
		}, ErrOwnership},
	} {
		t.Run(test.name, func(t *testing.T) {
			c, router := fixture(t)
			ctx := context.Background()
			if err := c.Ensure(ctx, testSOCKS); err != nil {
				t.Fatal(err)
			}
			test.modify(router)
			router.writes = nil
			if err := c.Cleanup(ctx); !errors.Is(err, test.want) {
				t.Fatalf("cleanup err = %v, want %v", err, test.want)
			}
			if len(router.writes) != 0 {
				t.Fatalf("foreign state was written: %v", router.writes)
			}
			if r, err := c.load(); err != nil || r == nil {
				t.Fatalf("lost evidence: %#v, %v", r, err)
			}
		})
	}
}

func TestCreateRetainsProofWhenSaveFails(t *testing.T) {
	c, router := fixture(t)
	ctx := context.Background()
	router.failSave = true
	if err := c.Ensure(ctx, testSOCKS); err == nil {
		t.Fatal("expected save failure")
	}
	before, err := c.load()
	if err != nil || before == nil || before.Phase != creating {
		t.Fatalf("lost creation proof: %#v, %v", before, err)
	}
	router.failSave = false
	if err := c.Ensure(ctx, testSOCKS); err != nil {
		t.Fatal(err)
	}
	after, err := c.load()
	if err != nil || after == nil || after.Phase != managed || before.Description != after.Description {
		t.Fatalf("ownership changed after retry: %#v, %v", after, err)
	}
}
