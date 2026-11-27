package servers

import (
	"context"
	"encoding/json"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// This verifies that the project's pinned binary can build the emitted
// outbounds. Xray does not connect to a target in run -test mode.
func TestVLESSShareLinkXrayConfig(t *testing.T) {
	binary := os.Getenv("BRORAY_XRAY_BIN")
	if binary == "" {
		t.Skip("BRORAY_XRAY_BIN is needed for config validation")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	version, err := exec.CommandContext(ctx, binary, "version").Output()
	if err != nil || !strings.HasPrefix(string(version), "Xray 26.11.9 ") {
		t.Fatalf("expected Xray 26.11.9: %s %v", version, err)
	}

	check := func(label, link string) {
		t.Helper()
		t.Run(label, func(t *testing.T) {
			profile, err := ParseLink(link)
			if err != nil {
				t.Fatalf("parse failed: %v", err)
			}
			raw, err := json.Marshal(XrayConfig(profile, "127.0.0.1", 1080, "warning", "none", "none"))
			if err != nil {
				t.Fatal(err)
			}
			path := filepath.Join(t.TempDir(), "config.json")
			if err := os.WriteFile(path, raw, 0o600); err != nil {
				t.Fatal(err)
			}
			ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
			defer cancel()
			output, err := exec.CommandContext(ctx, binary, "run", "-test", "-config", path).CombinedOutput()
			if err != nil {
				t.Fatalf("Xray rejected an accepted link: %v\n%s", err, output)
			}
		})
	}

	for _, network := range []string{"raw", "ws", "grpc", "httpupgrade", "xhttp", "kcp"} {
		for _, security := range []string{"none", "tls", "reality"} {
			if security == "reality" && network != "raw" && network != "grpc" && network != "xhttp" {
				continue
			}
			check(network+"/"+security, vlessMatrixLink(network, security, nil))
		}
	}
	for _, security := range []string{"none", "tls", "reality"} {
		for _, mode := range []string{"packet-up", "stream-up", "stream-one"} {
			check("xhttp/"+security+"/"+mode, vlessMatrixLink("xhttp", security, url.Values{"mode": {mode}}))
		}
		for _, mode := range []string{"gun", "multi"} {
			check("grpc/"+security+"/"+mode, vlessMatrixLink("grpc", security, url.Values{"mode": {mode}, "serviceName": {"fixture"}}))
		}
	}
	for _, security := range []string{"tls", "reality"} {
		for _, flow := range []string{"xtls-rprx-vision", "xtls-rprx-vision-udp443"} {
			check("raw/"+security+"/"+flow, vlessMatrixLink("raw", security, url.Values{"flow": {flow}}))
		}
	}
	for _, mode := range []string{"native", "xorpub", "random"} {
		for _, roundTrip := range []string{"0rtt", "1rtt"} {
			value := "mlkem768x25519plus." + mode + "." + roundTrip + "." + vlessMatrixKey
			check("encryption/"+mode+"/"+roundTrip, vlessMatrixLink("raw", "tls", url.Values{"encryption": {value}}))
		}
	}
	check("raw-header", vlessMatrixLink("raw", "none", url.Values{"header": {`{"type":"http","request":{"path":["/fixture"]}}`}}))
	check("tls-pin", vlessMatrixLink("raw", "tls", url.Values{"pcs": {strings.Repeat("de", 32)}, "vcn": {"cert.example.test"}}))
	check("mkcp-legacy", vlessMatrixLink("kcp", "none", url.Values{"mtu": {"1400"}, "seed": {"fixture"}}))
	check("ws-options", vlessMatrixLink("ws", "tls", url.Values{
		"streamOptions": {`{"wsSettings":{"headers":{"X-Test":"fixture"},"heartbeatPeriod":0}}`},
	}))
	check("xhttp-padding", vlessMatrixLink("xhttp", "tls", url.Values{"x_padding_bytes": {"100-1000"}}))
	// The pinned Xray requires encryption for a public IP literal.
	check("raw-ipv6-tls", strings.Replace(vlessMatrixLink("raw", "tls", nil), "origin.example.test", "[2001:db8::1]", 1))
	check("raw-ipv6-private", strings.Replace(vlessMatrixLink("raw", "none", nil), "origin.example.test", "[fd00::1]", 1))
}
