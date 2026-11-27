package servers

import (
	"encoding/base64"
	"encoding/json"
	"net/url"
	"strings"
	"testing"
)

const vlessMatrixID = "00000000-0000-4000-8000-000000000001"
const vlessMatrixKey = "E75P6uryBMf9M1j8nAByGIHRdCeBKCJ-xnTzf3_pe20"

func vlessMatrixLink(network, security string, options url.Values) string {
	q := url.Values{}
	if network != "" {
		q.Set("type", network)
	}
	if security != "" {
		q.Set("security", security)
	}
	if security == "reality" {
		q.Set("sni", "front.example.test")
		q.Set("pbk", vlessMatrixKey)
		q.Set("sid", "0123456789abcdef")
	}
	for key, values := range options {
		q[key] = values
	}
	return "vless://" + vlessMatrixID + "@origin.example.test:443?" +
		strings.ReplaceAll(q.Encode(), "+", "%20") + "#synthetic"
}

func vlessMatrixOutbound(t *testing.T, link string) map[string]any {
	t.Helper()
	server, err := ParseLink(link)
	if err != nil {
		t.Fatalf("valid synthetic link rejected: %v", err)
	}
	return Outbound(server)
}

func vlessMatrixField(t *testing.T, object map[string]any, key string) map[string]any {
	t.Helper()
	field, ok := object[key].(map[string]any)
	if !ok {
		t.Fatalf("expected %s object, got %v", key, object[key])
	}
	return field
}

func vlessMatrixEqual(t *testing.T, field string, got, want any) {
	t.Helper()
	actual, err := json.Marshal(got)
	if err != nil {
		t.Fatal(err)
	}
	expected, err := json.Marshal(want)
	if err != nil {
		t.Fatal(err)
	}
	if string(actual) != string(expected) {
		t.Errorf("%s = %s, want %s", field, actual, expected)
	}
}

// BROray v3.5.10 areas/servers/parser_combinations_test.go and parse.go.
// The Cartesian domain covers all ordinary URI transports, native-only
// selectors, and invalid selectors. Every admitted case checks Xray output.
func TestVLESSShareLinkSelectorMatrix(t *testing.T) {
	for _, transport := range []struct {
		name        string
		ordinary    bool
		withReality bool
	}{
		{"raw", true, true}, {"ws", true, false}, {"grpc", true, true},
		{"httpupgrade", true, false}, {"xhttp", true, true}, {"kcp", true, false},
		{"xdrive", false, false}, {"masque", false, false}, {"invalid", false, false},
	} {
		for _, security := range []string{"none", "tls", "reality", "invalid"} {
			t.Run(transport.name+"/"+security, func(t *testing.T) {
				link := vlessMatrixLink(transport.name, security, nil)
				if !transport.ordinary || security == "invalid" || (security == "reality" && !transport.withReality) {
					if _, err := ParseLink(link); err == nil {
						t.Fatal("unsupported selector combination accepted")
					}
					return
				}
				out := vlessMatrixOutbound(t, link)
				vlessMatrixEqual(t, "protocol", out["protocol"], "vless")
				vlessMatrixEqual(t, "settings", out["settings"], map[string]any{
					"vnext": []any{map[string]any{
						"address": "origin.example.test", "port": 443,
						"users": []any{map[string]any{"id": vlessMatrixID, "encryption": "none"}},
					}},
				})
				stream := vlessMatrixField(t, out, "streamSettings")
				vlessMatrixEqual(t, "network", stream["network"], transport.name)
				vlessMatrixEqual(t, "security", stream["security"], security)
				vlessMatrixField(t, stream, transport.name+"Settings")
				switch security {
				case "tls":
					vlessMatrixEqual(t, "tlsSettings", stream["tlsSettings"], map[string]any{
						"serverName": "origin.example.test", "fingerprint": "chrome",
					})
				case "reality":
					vlessMatrixEqual(t, "realitySettings", stream["realitySettings"], map[string]any{
						"serverName": "front.example.test", "fingerprint": "chrome",
						"publicKey": vlessMatrixKey, "shortId": "0123456789abcdef",
					})
				case "none":
					vlessMatrixEqual(t, "tlsSettings", stream["tlsSettings"], nil)
					vlessMatrixEqual(t, "realitySettings", stream["realitySettings"], nil)
				}
			})
		}
	}
}

// parseVless in the donor gates Vision by protection and transport, with an
// exception for supported VLESS encryption on otherwise compatible streams.
func TestVLESSShareLinkVisionMatrix(t *testing.T) {
	for _, network := range []string{"raw", "ws", "grpc", "httpupgrade", "xhttp", "kcp"} {
		for _, security := range []string{"none", "tls", "reality"} {
			for _, flow := range []string{"xtls-rprx-vision", "xtls-rprx-vision-udp443"} {
				t.Run(network+"/"+security+"/"+flow, func(t *testing.T) {
					link := vlessMatrixLink(network, security, url.Values{"flow": {flow}})
					if network != "raw" || security == "none" {
						if _, err := ParseLink(link); err == nil {
							t.Fatal("inapplicable Vision flow accepted")
						}
						return
					}
					assertVLESSMatrixUser(t, link, "none", flow)
				})
			}
		}
	}
	for _, mode := range []string{"native", "xorpub", "random"} {
		for _, roundTrip := range []string{"0rtt", "1rtt"} {
			t.Run(mode+"/"+roundTrip, func(t *testing.T) {
				encryption := "mlkem768x25519plus." + mode + "." + roundTrip + "." + vlessMatrixKey
				flow := "xtls-rprx-vision"
				assertVLESSMatrixUser(t, vlessMatrixLink("ws", "tls", url.Values{
					"encryption": {encryption}, "flow": {flow},
				}), encryption, flow)
			})
		}
	}
}

func assertVLESSMatrixUser(t *testing.T, link, encryption, flow string) {
	t.Helper()
	out := vlessMatrixOutbound(t, link)
	vlessMatrixEqual(t, "settings", out["settings"], map[string]any{
		"vnext": []any{map[string]any{
			"address": "origin.example.test", "port": 443,
			"users": []any{map[string]any{"id": vlessMatrixID, "encryption": encryption, "flow": flow}},
		}},
	})
}

func TestVLESSShareLinkAliasesAndModes(t *testing.T) {
	for _, alias := range [][2]string{
		{"", "raw"}, {"tcp", "raw"}, {"websocket", "ws"},
		{"httpUpgrade", "httpupgrade"}, {"splithttp", "xhttp"},
	} {
		t.Run("transport/"+alias[0], func(t *testing.T) {
			got := vlessMatrixOutbound(t, vlessMatrixLink(alias[0], "tls", nil))
			want := vlessMatrixOutbound(t, vlessMatrixLink(alias[1], "tls", nil))
			vlessMatrixEqual(t, "alias outbound", got, want)
		})
	}
	vlessMatrixEqual(t, "omitted security",
		vlessMatrixOutbound(t, vlessMatrixLink("raw", "", nil)),
		vlessMatrixOutbound(t, vlessMatrixLink("raw", "none", nil)))

	for _, tc := range []struct {
		network, mode string
		valid         bool
	}{
		{"xhttp", "auto", true}, {"xhttp", "packet-up", true}, {"xhttp", "stream-up", true},
		{"xhttp", "stream-one", true}, {"xhttp", "gun", false}, {"xhttp", "multi", false},
		{"xhttp", "invalid", false}, {"grpc", "gun", true}, {"grpc", "multi", true},
		{"grpc", "auto", false}, {"grpc", "packet-up", false}, {"grpc", "invalid", false},
	} {
		t.Run(tc.network+"/"+tc.mode, func(t *testing.T) {
			link := vlessMatrixLink(tc.network, "tls", url.Values{"mode": {tc.mode}})
			if !tc.valid {
				if _, err := ParseLink(link); err == nil {
					t.Fatal("unsupported transport mode accepted")
				}
				return
			}
			stream := vlessMatrixField(t, vlessMatrixOutbound(t, link), "streamSettings")
			block := vlessMatrixField(t, stream, tc.network+"Settings")
			if tc.network == "grpc" {
				vlessMatrixEqual(t, "multiMode", block["multiMode"], tc.mode == "multi")
			} else {
				vlessMatrixEqual(t, "mode", block["mode"], tc.mode)
			}
		})
	}
	for _, key := range []string{"serviceName", "service_name"} {
		t.Run(key, func(t *testing.T) {
			stream := vlessMatrixField(t, vlessMatrixOutbound(t, vlessMatrixLink("grpc", "tls", url.Values{
				key: {"example+rpc"}, "authority": {"grpc.example.test"}, "host": {"grpc.example.test"},
			})), "streamSettings")
			block := vlessMatrixField(t, stream, "grpcSettings")
			vlessMatrixEqual(t, "serviceName", block["serviceName"], "example+rpc")
			vlessMatrixEqual(t, "authority", block["authority"], "grpc.example.test")
		})
	}
}

// Advanced URI fields and their Xray names come from the donor's
// parseStreamExtensions, auditQuery, streamOptionsError, and xrayconfig.go.
func TestVLESSShareLinkAdvancedFields(t *testing.T) {
	pqv := base64.RawURLEncoding.EncodeToString(make([]byte, 1952))
	pin := strings.Repeat("de", 32)
	for _, tc := range []struct {
		name, network, security string
		options                 url.Values
		block                   string
		want                    map[string]any
	}{
		{"raw-http", "raw", "none", url.Values{
			"headerType": {"http"}, "host": {"one.example.test,two.example.test"}, "path": {"/front"},
		}, "rawSettings", map[string]any{"header": map[string]any{
			"type": "http", "request": map[string]any{"path": []string{"/front"},
				"headers": map[string]any{"Host": []string{"one.example.test", "two.example.test"}}},
		}}},
		{"raw-header-object", "raw", "none", url.Values{
			"header": {`{"type":"http","request":{"method":"GET","path":["/one","/two"]}}`},
		}, "rawSettings", map[string]any{"header": map[string]any{
			"type": "http", "request": map[string]any{"method": "GET", "path": []string{"/one", "/two"}},
		}}},
		{"ws-options", "ws", "tls", url.Values{
			"host": {"ws.example.test"}, "path": {"/socket?ed=2048"},
			"streamOptions": {`{"wsSettings":{"headers":{"X-Test":"synthetic"},"heartbeatPeriod":0}}`},
		}, "wsSettings", map[string]any{
			"host": "ws.example.test", "path": "/socket?ed=2048",
			"headers": map[string]any{"X-Test": "synthetic"}, "heartbeatPeriod": 0,
		}},
		{"upgrade-options", "httpupgrade", "tls", url.Values{
			"host": {"upgrade.example.test"}, "path": {"/upgrade"},
			"streamOptions": {`{"httpupgradeSettings":{"headers":{"X-Test":"synthetic"}}}`},
		}, "httpupgradeSettings", map[string]any{
			"host": "upgrade.example.test", "path": "/upgrade", "headers": map[string]any{"X-Test": "synthetic"},
		}},
		{"grpc-options", "grpc", "tls", url.Values{
			"streamOptions": {`{"grpcSettings":{"idle_timeout":0,"health_check_timeout":5,"permit_without_stream":false,"initial_windows_size":65536,"user_agent":"synthetic"}}`},
		}, "grpcSettings", map[string]any{
			"idle_timeout": 0, "health_check_timeout": 5, "permit_without_stream": false,
			"initial_windows_size": 65536, "user_agent": "synthetic",
		}},
		{"socket-options", "raw", "none", url.Values{
			"streamOptions": {`{"sockopt":{"tcpFastOpen":false,"tcpKeepAliveIdle":0,"tcpKeepAliveInterval":30,"domainStrategy":"UseIPv4"}}`},
		}, "sockopt", map[string]any{
			"tcpFastOpen": false, "tcpKeepAliveIdle": 0, "tcpKeepAliveInterval": 30, "domainStrategy": "UseIPv4",
		}},
		{"xhttp-extra", "xhttp", "tls", url.Values{
			"mode": {"packet-up"}, "path": {"/split"}, "host": {"split.example.test"},
			"extra":           {`{"scMaxEachPostBytes":"1000000","xPaddingBytes":"100-1000"}`},
			"x_padding_bytes": {"100-1000"},
		}, "xhttpSettings", map[string]any{
			"mode": "packet-up", "path": "/split", "host": "split.example.test",
			"extra": map[string]any{"scMaxEachPostBytes": "1000000", "xPaddingBytes": "100-1000"},
		}},
		{"xhttp-padding-alias", "xhttp", "tls", url.Values{"x_padding_bytes": {"100-1000"}},
			"xhttpSettings", map[string]any{"extra": map[string]any{"xPaddingBytes": "100-1000"}}},
		{"mkcp-options", "kcp", "none", url.Values{
			"mtu": {"1400"}, "tti": {"20"}, "uplinkCapacity": {"10"}, "downlinkCapacity": {"20"},
			"cwndMultiplier": {"2"}, "maxSendingWindow": {"2048"},
		}, "kcpSettings", map[string]any{
			"mtu": 1400, "tti": 20, "uplinkCapacity": 10, "downlinkCapacity": 20,
			"cwndMultiplier": 2, "maxSendingWindow": 2048,
		}},
		{"mkcp-empty-seed", "kcp", "none", url.Values{"seed": {""}},
			"finalmask", map[string]any{"udp": []any{map[string]any{"type": "mkcp-legacy", "settings": map[string]any{}}}}},
		{"final-mask", "raw", "none", url.Values{
			"fm": {`{"tcp":[{"type":"fragment","settings":{"length":"100-200"}}]}`},
		}, "finalmask", map[string]any{"tcp": []any{
			map[string]any{"type": "fragment", "settings": map[string]any{"length": "100-200"}},
		}}},
		{"mkcp-legacy-dns", "kcp", "none", url.Values{
			"seed": {"synthetic-seed"}, "headerType": {"dns"}, "host": {"dns.example.test"},
		}, "finalmask", map[string]any{"udp": []any{
			map[string]any{"type": "mkcp-legacy", "settings": map[string]any{"value": "synthetic-seed"}},
			map[string]any{"type": "mkcp-legacy", "settings": map[string]any{"header": "dns", "value": "dns.example.test"}},
		}}},
		{"tls-verification", "raw", "tls", url.Values{
			"sni": {"tls.example.test"}, "fp": {"firefox"}, "alpn": {"h2,http/1.1"},
			"ech": {"synthetic"}, "vcn": {"cert.example.test"}, "pcs": {pin}, "insecure": {"false"},
		}, "tlsSettings", map[string]any{
			"serverName": "tls.example.test", "fingerprint": "firefox", "alpn": []string{"h2", "http/1.1"},
			"echConfigList": "synthetic", "verifyPeerCertByName": "cert.example.test", "pinnedPeerCertSha256": pin,
		}},
		{"reality-verification", "raw", "reality", url.Values{
			"spx": {"/synthetic?plus=a+b"}, "pqv": {pqv},
		}, "realitySettings", map[string]any{"spiderX": "/synthetic?plus=a+b", "mldsa65Verify": pqv}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			stream := vlessMatrixField(t, vlessMatrixOutbound(t, vlessMatrixLink(tc.network, tc.security, tc.options)), "streamSettings")
			block := vlessMatrixField(t, stream, tc.block)
			for field, want := range tc.want {
				vlessMatrixEqual(t, tc.block+"."+field, block[field], want)
			}
		})
	}
}

func TestVLESSShareLinkRejectsConflictsAndLoss(t *testing.T) {
	for _, tc := range []struct {
		name, network, security string
		options                 url.Values
	}{
		{"duplicate-selector", "raw", "tls", url.Values{"type": {"raw", "raw"}}},
		{"duplicate-service-alias", "grpc", "tls", url.Values{"serviceName": {"rpc"}, "service_name": {"rpc"}}},
		{"duplicate-insecure-alias", "raw", "tls", url.Values{"allowInsecure": {"false"}, "insecure": {"false"}}},
		{"grpc-authority-conflict", "grpc", "tls", url.Values{"authority": {"one.example.test"}, "host": {"two.example.test"}}},
		{"raw-header-conflict", "raw", "none", url.Values{"header": {`{"type":"none"}`}, "path": {"/front"}}},
		{"xhttp-padding-conflict", "xhttp", "tls", url.Values{"x_padding_bytes": {"100-1000"}, "extra": {`{"xPaddingBytes":"200-1000"}`}}},
		{"xhttp-padding-bound", "xhttp", "tls", url.Values{"x_padding_bytes": {"0-1"}}},
		{"xhttp-extra-object", "xhttp", "tls", url.Values{"extra": {`[]`}}},
		{"xhttp-extra-unknown", "xhttp", "tls", url.Values{"extra": {`{"unused":true}`}}},
		{"extra-inactive", "ws", "tls", url.Values{"extra": {`{"xPaddingBytes":"100-1000"}`}}},
		{"raw-host-inactive", "raw", "tls", url.Values{"host": {"other.example.test"}}},
		{"grpc-path-inactive", "grpc", "tls", url.Values{"path": {"/unused"}}},
		{"grpc-service-inactive", "ws", "tls", url.Values{"service_name": {"unused"}}},
		{"authority-inactive", "ws", "tls", url.Values{"authority": {"other.example.test"}}},
		{"sni-inactive", "ws", "none", url.Values{"sni": {"other.example.test"}}},
		{"reality-alpn-inactive", "raw", "reality", url.Values{"alpn": {"h2"}}},
		{"reality-key-inactive", "raw", "tls", url.Values{"pbk": {vlessMatrixKey}}},
		{"reality-missing-key", "raw", "reality", url.Values{"pbk": {""}}},
		{"reality-missing-sni", "raw", "reality", url.Values{"sni": {""}}},
		{"allow-insecure", "raw", "tls", url.Values{"allowInsecure": {"1"}}},
		{"insecure", "raw", "tls", url.Values{"insecure": {"true"}}},
		{"unsupported-encryption", "raw", "tls", url.Values{"encryption": {"auto"}}},
		{"invalid-encryption-round-trip", "raw", "tls", url.Values{"encryption": {"mlkem768x25519plus.native.2rtt." + vlessMatrixKey}}},
		{"unsupported-flow", "raw", "tls", url.Values{"flow": {"xtls-rprx-direct"}}},
		{"mkcp-seed-inactive", "raw", "none", url.Values{"seed": {""}}},
		{"mkcp-retired-option", "kcp", "none", url.Values{"congestion": {"false"}}},
		{"mkcp-invalid-integer", "kcp", "none", url.Values{"mtu": {"1.5"}}},
		{"mkcp-window-bound", "kcp", "none", url.Values{"mtu": {"1400"}, "maxSendingWindow": {"1399"}}},
		{"final-mask-unknown-type", "raw", "none", url.Values{"fm": {`{"tcp":[{"type":"bogus"}]}`}}},
		{"final-mask-invalid-json", "raw", "none", url.Values{"fm": {"invalid"}}},
		{"ws-host-header-conflict", "ws", "tls", url.Values{"streamOptions": {`{"wsSettings":{"headers":{"Host":"other.example.test"}}}`}}},
		{"ws-heartbeat-bound", "ws", "tls", url.Values{"streamOptions": {`{"wsSettings":{"heartbeatPeriod":-1}}`}}},
		{"socket-field-type", "raw", "none", url.Values{"streamOptions": {`{"sockopt":{"tcpFastOpen":"false"}}`}}},
		{"socket-unsupported-mark", "raw", "none", url.Values{"streamOptions": {`{"sockopt":{"mark":123}}`}}},
		{"unknown-query", "raw", "tls", url.Values{"unknownField": {"synthetic-value"}}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			if _, err := ParseLink(vlessMatrixLink(tc.network, tc.security, tc.options)); err == nil {
				t.Fatal("conflicting, inactive, or unsupported option accepted")
			}
		})
	}
	// The three supported streamOptions transport objects are accepted only
	// on their active transport (donor TestClientInactiveStreamBlocks).
	for _, network := range []string{"raw", "ws", "grpc", "httpupgrade", "xhttp", "kcp"} {
		for _, optionsNetwork := range []string{"ws", "grpc", "httpupgrade"} {
			if optionsNetwork == network {
				continue
			}
			t.Run(network+"/"+optionsNetwork+"Settings", func(t *testing.T) {
				value := `{"` + optionsNetwork + `Settings":{}}`
				if _, err := ParseLink(vlessMatrixLink(network, "tls", url.Values{"streamOptions": {value}})); err == nil {
					t.Fatal("inactive stream settings accepted")
				}
			})
		}
	}
}

// The donor's parse_ref_data_test.go and uri.go cover slash handling and
// percent decoding separately from the transport matrix.
func TestVLESSShareLinkURIEncoding(t *testing.T) {
	link := "vless://" + vlessMatrixID + "@origin.example.test:8443/?type=ws&security=tls&path=%2Fone+two&alpn=h2,http%2F1.1,#one+two"
	server, err := ParseLink(link)
	if err != nil {
		t.Fatal(err)
	}
	vlessMatrixEqual(t, "name", server.Name, "one+two")
	out := Outbound(server)
	stream := vlessMatrixField(t, out, "streamSettings")
	vlessMatrixEqual(t, "path", vlessMatrixField(t, stream, "wsSettings")["path"], "/one+two")
	vlessMatrixEqual(t, "alpn", vlessMatrixField(t, stream, "tlsSettings")["alpn"], []string{"h2", "http/1.1"})
	for _, suffix := range []string{":443/path?type=ws", ":443?type=ws&path=%ZZ", ":443#x%00", ":443#x%0A", ":0", ":65536", ""} {
		t.Run(suffix, func(t *testing.T) {
			if _, err := ParseLink("vless://" + vlessMatrixID + "@origin.example.test" + suffix); err == nil {
				t.Fatal("malformed VLESS URI accepted")
			}
		})
	}
}
