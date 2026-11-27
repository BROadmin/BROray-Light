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

const webListen = "192.168.1.1:8080"
const webURL = "https://brolight.test-router.netcraze.link/"
const anotherWebsite = "ip http proxy other\n    upstream http 192.168.1.22 8000\n    domain ndns\n!\n"
const outsideWeb = routerBase + foreignProxy + anotherWebsite

type webRouterFake struct {
	running, startup              string
	ndns                          string
	writes                        []string
	failSave, omitSSL, omitDomain bool
	unknownSave                   bool
	after                         func(string)
}

func (f *webRouterFake) run(_ context.Context, command string) (string, error) {
	switch command {
	case "show interface Bridge0":
		return "type: Bridge\naddress: 192.168.1.1\n", nil
	case "show ndns":
		return f.ndns, nil
	case "show running-config":
		return f.running, nil
	case "more startup-config":
		return f.startup, nil
	}
	f.writes = append(f.writes, command)
	switch {
	case command == "system configuration save":
		if f.unknownSave {
			return "", context.DeadlineExceeded
		}
		if f.failSave {
			return "no such command: save", nil
		}
		f.startup = f.running
	case command == webRule:
		f.running += webRule + "\n    security-level private\n"
		if !f.omitSSL {
			f.running += "    ssl redirect\n"
		}
		f.running += "!\n"
	case command == "no "+webRule:
		i := strings.Index(f.running, "\n"+webRule+"\n")
		if i == -1 {
			return "", errors.New("unexpected deletion")
		}
		end := strings.Index(f.running[i+1:], "\n!\n")
		if end == -1 {
			return "", errors.New("unexpected configuration")
		}
		f.running = f.running[:i+1] + f.running[i+end+4:]
	case strings.HasPrefix(command, webRule+" "):
		line := strings.TrimPrefix(command, webRule+" ")
		switch line {
		case "ssl redirect":
		case "security-level public":
			f.running = strings.Replace(f.running, "    security-level private\n    ssl redirect\n",
				"    security-level public\n    ssl redirect\n", 1)
		case "domain ndns":
			if !f.omitDomain {
				f.running = strings.TrimSuffix(f.running, "!\n") + "    domain ndns\n!\n"
			}
		default:
			f.running = strings.TrimSuffix(f.running, "!\n") + "    " + line + "\n!\n"
		}
	default:
		return "", errors.New("unexpected write: " + command)
	}
	if f.after != nil {
		f.after(command)
	}
	return "", nil
}

func webFixture(t *testing.T) (*Client, *webRouterFake) {
	t.Helper()
	f := &webRouterFake{running: outsideWeb, startup: outsideWeb, ndns: "name: test-router\ndomain: netcraze.link\naccess: cloud\n"}
	c := New(t.TempDir())
	c.run, c.settle = f.run, 0
	return c, f
}

func TestRemoteAccessEnableAndRemoveOnlyOwnedPublication(t *testing.T) {
	ctx := context.Background()
	c, f := webFixture(t)
	initial, err := c.RemoteAccess(ctx, webListen)
	if err != nil || initial.State != "disabled" || !initial.CanEnable || initial.URL != "" || len(f.writes) != 0 {
		t.Fatalf("initial: %+v, %v, writes %v", initial, err, f.writes)
	}
	enabled, err := c.SetRemoteAccess(ctx, webListen, true)
	if err != nil || enabled.State != "enabled" || enabled.URL != webURL || !enabled.CanDisable || enabled.CanEnable {
		t.Fatalf("enabled: %+v, %v", enabled, err)
	}
	want := []string{webRule, webRule + " ssl redirect", webRule + " upstream http 192.168.1.1 8080",
		webRule + " security-level public", webRule + " domain ndns", "system configuration save"}
	if !slices.Equal(f.writes, want) || f.running != f.startup || !strings.HasPrefix(f.running, outsideWeb) {
		t.Fatalf("unexpected configuration or commands: %v", f.writes)
	}
	f.writes = nil
	if got, err := c.SetRemoteAccess(ctx, webListen, true); err != nil || got != enabled || len(f.writes) != 0 {
		t.Fatalf("enable is not idempotent: %+v, %v, %v", got, err, f.writes)
	}
	disabled, err := c.SetRemoteAccess(ctx, webListen, false)
	if err != nil || disabled != initial || f.running != outsideWeb || f.startup != outsideWeb ||
		!slices.Equal(f.writes, []string{"no " + webRule, "system configuration save"}) {
		t.Fatalf("disable: %+v, %v, writes %v", disabled, err, f.writes)
	}
	if _, err := os.Lstat(filepath.Join(c.stateDir, webReceiptFile)); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("receipt retained after completed cleanup: %v", err)
	}
}

func TestRemoteAccessDoesNotWriteUnprovedOrInconsistentSettings(t *testing.T) {
	for _, test := range []struct {
		name, state, listen string
		setup               func(*webRouterFake)
	}{
		{"matching foreign rule", "conflict", webListen, func(f *webRouterFake) {
			f.running += webRule + "\n    upstream http 192.168.1.1 8080\n    domain ndns\n    ssl redirect\n    security-level public\n!\n"
			f.startup = f.running
		}},
		{"foreign rule startup only", "conflict", webListen, func(f *webRouterFake) {
			f.startup += webRule + "\n    upstream http 192.168.1.45 8080\n!\n"
		}},
		{"different case", "conflict", webListen, func(f *webRouterFake) {
			f.running += "ip http proxy BROlight\n    upstream http 192.168.1.45 8080\n!\n"
			f.startup = f.running
		}},
		{"outside reference", "conflict", webListen, func(f *webRouterFake) {
			f.running += "some other command brolight\n!\n"
			f.startup = f.running
		}},
		{"unsaved changes", "conflict", webListen, func(f *webRouterFake) {
			f.running += "ip route 192.168.111.0 255.255.255.0 192.168.1.44\n!\n"
		}},
		{"unsafe registered name", "unavailable", webListen, func(f *webRouterFake) {
			f.ndns = "name: user/path\ndomain: netcraze.link\naccess: cloud\n"
		}},
		{"duplicate registered name", "unavailable", webListen, func(f *webRouterFake) {
			f.ndns += "name: other\n"
		}},
		{"wrong LAN interface", "unavailable", "192.168.1.55:8080", func(*webRouterFake) {}},
		{"loopback", "unavailable", "127.0.0.1:8080", func(*webRouterFake) {}},
	} {
		t.Run(test.name, func(t *testing.T) {
			ctx := context.Background()
			c, f := webFixture(t)
			test.setup(f)
			for _, enable := range []bool{true, false} {
				got, _ := c.SetRemoteAccess(ctx, test.listen, enable)
				if got.State != test.state || got.URL != "" || got.CanEnable || got.CanDisable || len(f.writes) != 0 {
					t.Fatalf("unsafe change with enable=%t: %+v, writes=%v", enable, got, f.writes)
				}
			}
		})
	}
}

func TestRemoteAccessCreateFailureRollsBackVerifiedBlock(t *testing.T) {
	for _, test := range []struct {
		name  string
		setup func(*webRouterFake)
	}{
		{"save", func(f *webRouterFake) { f.failSave = true }},
		{"SSL not serialized", func(f *webRouterFake) { f.omitSSL = true }},
		{"NDNS association not serialized", func(f *webRouterFake) { f.omitDomain = true }},
	} {
		t.Run(test.name, func(t *testing.T) {
			c, f := webFixture(t)
			test.setup(f)
			got, err := c.SetRemoteAccess(context.Background(), webListen, true)
			if err == nil || got.State != "disabled" || got.URL != "" ||
				f.running != outsideWeb || f.startup != outsideWeb || f.writes[len(f.writes)-1] != "no "+webRule {
				t.Fatalf("unsafe rollback: %+v, %v, commands %v", got, err, f.writes)
			}
			if f.omitSSL && slices.Contains(f.writes, webRule+" domain ndns") {
				t.Fatal("published rule before TLS redirect was proved")
			}
		})
	}
}

func TestRemoteAccessDoesNotRollbackUnknownRule(t *testing.T) {
	c, f := webFixture(t)
	f.after = func(command string) {
		if command == webRule+" ssl redirect" {
			f.running = strings.TrimSuffix(f.running, "!\n") + "    ssl enable\n!\n"
		}
	}
	ctx := context.Background()
	got, err := c.SetRemoteAccess(ctx, webListen, true)
	if err == nil || got.State != "recovery" || got.URL != "" || got.CanDisable || got.CanEnable {
		t.Fatalf("unexpected recovery: %+v, %v", got, err)
	}
	for _, enable := range []bool{true, false} {
		if _, err := c.SetRemoteAccess(ctx, webListen, enable); err == nil {
			t.Fatal("changed unknown partial rule")
		}
	}
	if !slices.Equal(f.writes, []string{webRule, webRule + " ssl redirect"}) ||
		!strings.Contains(f.running, "ssl enable") || f.startup != outsideWeb {
		t.Fatalf("unexpected writes: %v", f.writes)
	}
	if r, err := c.readWebReceipt(); err != nil || r == nil || r.Phase != creating || r.Step != 1 {
		t.Fatalf("lost pending state: %#v, %v", r, err)
	}
}

func TestRemoteAccessDisableCanResumeAfterSaveFailure(t *testing.T) {
	ctx := context.Background()
	c, f := webFixture(t)
	if _, err := c.SetRemoteAccess(ctx, webListen, true); err != nil {
		t.Fatal(err)
	}
	f.failSave, f.ndns = true, ""
	got, err := c.SetRemoteAccess(ctx, webListen, false)
	if err == nil || got.State != "recovery" || !got.CanDisable || got.CanEnable || got.URL != "" ||
		f.running != outsideWeb || f.startup == outsideWeb {
		t.Fatalf("failed delete lost recovery state: %+v, %v", got, err)
	}
	restarted := New(c.stateDir)
	restarted.run, restarted.settle = f.run, 0
	f.failSave, f.writes = false, nil
	got, err = restarted.SetRemoteAccess(ctx, webListen, false)
	if err != nil || got.State != "unavailable" || f.running != outsideWeb || f.startup != outsideWeb ||
		!slices.Equal(f.writes, []string{"system configuration save"}) {
		t.Fatalf("disable retry reissued deletion or changed other settings: %+v, %v, %v", got, err, f.writes)
	}
}

func TestRemoteAccessDoesNotSaveUnrelatedChangeDuringPublish(t *testing.T) {
	c, f := webFixture(t)
	f.after = func(command string) {
		if command == webRule+" domain ndns" {
			f.running += "ip route 192.168.111.0 255.255.255.0 192.168.1.44\n!\n"
		}
	}
	got, err := c.SetRemoteAccess(context.Background(), webListen, true)
	if err == nil || got.State != "recovery" || f.startup != outsideWeb ||
		slices.Contains(f.writes, "system configuration save") || slices.Contains(f.writes, "no "+webRule) {
		t.Fatalf("unrelated edit was committed or deleted: %+v, %v, writes %v", got, err, f.writes)
	}
}

func TestRemoteAccessRetainsProofWhileLateSaveIsUnresolved(t *testing.T) {
	ctx := context.Background()
	c, f := webFixture(t)
	f.unknownSave = true
	got, err := c.SetRemoteAccess(ctx, webListen, true)
	if err == nil || got.State != "recovery" || got.CanEnable || got.CanDisable ||
		f.startup != outsideWeb || !strings.Contains(f.running, webRule+"\n") ||
		slices.Contains(f.writes, "no "+webRule) {
		t.Fatalf("lost ownership of possible late publication: %+v, %v, writes %v", got, err, f.writes)
	}
	restarted := New(c.stateDir)
	restarted.run, restarted.settle = f.run, 0
	f.writes = nil
	if got, err := restarted.SetRemoteAccess(ctx, webListen, false); err == nil || got.CanDisable || len(f.writes) != 0 {
		t.Fatalf("unresolved save allowed deletion: %+v, %v, writes %v", got, err, f.writes)
	}
	f.unknownSave, f.startup = false, f.running
	if got, err := restarted.SetRemoteAccess(ctx, webListen, true); err != nil || got.State != "enabled" ||
		got.URL != webURL || len(f.writes) != 0 {
		t.Fatalf("late successful save was rewritten or lost: %+v, %v, writes %v", got, err, f.writes)
	}
	f.unknownSave = true
	got, err = restarted.SetRemoteAccess(ctx, webListen, false)
	if err == nil || got.State != "recovery" || got.CanDisable || f.running != outsideWeb || f.startup == f.running {
		t.Fatalf("uncertain removal was treated as complete: %+v, %v", got, err)
	}
	f.unknownSave, f.startup, f.writes = false, f.running, nil
	got, err = restarted.SetRemoteAccess(ctx, webListen, false)
	if err != nil || got.State != "disabled" || len(f.writes) != 0 {
		t.Fatalf("verified late removal was not finalized: %+v, %v, writes %v", got, err, f.writes)
	}
}

func TestRemoteAccessReportsLostDomainAfterSuccessfulSave(t *testing.T) {
	ctx := context.Background()
	c, f := webFixture(t)
	f.after = func(command string) {
		if command == "system configuration save" {
			f.ndns = ""
		}
	}
	got, err := c.SetRemoteAccess(ctx, webListen, true)
	if !errors.Is(err, ErrWebUnavailable) || got.URL != "" || got.State != "unavailable" ||
		!got.CanDisable || f.startup != f.running || !strings.Contains(f.running, webRule+"\n") {
		t.Fatalf("reported stale publication URL: %+v, %v", got, err)
	}
}
