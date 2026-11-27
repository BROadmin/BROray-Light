package lightapp

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"sync/atomic"
	"testing"
)

func TestSubscriptionURIHTTPSVLESS(t *testing.T) {
	const (
		raw   = "vless://11111111-1111-4111-8111-111111111111@first.example:443?type=tcp&security=tls#First%20node"
		xhttp = "vless://22222222-2222-4222-8222-222222222222@second.example:8443?type=splithttp&security=tls&sni=cdn.example&path=%2Fconnect#Second%20node"
	)
	a, runtime, _ := newTestApp(t)
	type reply struct {
		status int
		body   string
	}
	var response atomic.Pointer[reply]
	var requests atomic.Int32
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests.Add(1)
		if r.TLS == nil || r.Method != http.MethodGet || r.URL.Path != "/feeds/vless" || r.URL.RawQuery != "key=fixture%2Btoken" {
			http.Error(w, "unexpected subscription request", http.StatusBadRequest)
			return
		}
		current := response.Load()
		w.WriteHeader(current.status)
		_, _ = io.WriteString(w, current.body)
	}))
	t.Cleanup(server.Close)

	// Trust the test server certificate while keeping the production redirect
	// policy. This test and the other subscription-client tests run serially.
	original := subscriptionHTTP
	client := *original
	client.Transport = server.Client().Transport
	subscriptionHTTP = &client
	t.Cleanup(func() { subscriptionHTTP = original })

	subscriptionURI := server.URL + "/feeds/vless?key=fixture%2Btoken"
	runAction := func(input action) error {
		t.Helper()
		body, err := json.Marshal(input)
		if err != nil {
			t.Fatal(err)
		}
		request := httptest.NewRequest(http.MethodPost, "/api/action", bytes.NewReader(body))
		request.Header.Set("Content-Type", "application/json")
		_, err = a.action(httptest.NewRecorder(), request)
		return err
	}
	if err := runAction(action{Kind: "subscription-save", Name: "HTTPS feed", URL: subscriptionURI}); err != nil {
		t.Fatal(err)
	}
	sub := a.state.Subscriptions[0].ID

	refresh := func(status int, body string) error {
		t.Helper()
		response.Store(&reply{status: status, body: body})
		return runAction(action{Kind: "subscription-refresh", ID: sub})
	}
	plain := "\ufeff# Subscription\r\n" + raw + "\r\n" + xhttp + "\r\n" +
		strings.Replace(raw, "#First%20node", "#Duplicate", 1) + "\r\n"
	if err := refresh(http.StatusOK, plain); err != nil {
		t.Fatal(err)
	}
	if len(a.state.Servers) != 2 {
		t.Fatalf("catalogue has %d entries, want two distinct profiles", len(a.state.Servers))
	}
	first, second := a.state.Servers[0].Profile, a.state.Servers[1].Profile
	if first.ID == "" || second.ID == "" || first.ID == second.ID ||
		first.Name != "First node" || first.Network != "raw" || first.Security != "tls" ||
		second.Name != "Second node" || second.Network != "xhttp" || second.Security != "tls" ||
		second.Transport.Path != "/connect" || second.TLS.ServerName != "cdn.example" {
		t.Fatalf("unexpected imported profiles: %v, %v", first.Summary(false), second.Summary(false))
	}
	if err := runAction(action{Kind: "activate", ID: second.ID}); err != nil {
		t.Fatal(err)
	}

	// A Unicode comment produces an alphabet-specific character in the fixture.
	// Choose its alignment and length so the padded and unpadded cases differ.
	encodedText := "\ufeff" + xhttp + "\r\n" + strings.Replace(raw, "#First%20node", "#Renamed%20by%20feed", 1) + "\r\n"
	for len(encodedText)%3 != 2 {
		encodedText += " "
	}
	encodedText += "#🌿"
	for len(encodedText)%3 == 0 {
		encodedText += " "
	}
	for _, tc := range []struct {
		name  string
		codec *base64.Encoding
	}{
		{"standard padded", base64.StdEncoding},
		{"standard raw", base64.RawStdEncoding},
		{"URL-safe padded", base64.URLEncoding},
		{"URL-safe raw", base64.RawURLEncoding},
	} {
		t.Run(tc.name, func(t *testing.T) {
			encoded := tc.codec.EncodeToString([]byte(encodedText))
			if !strings.ContainsAny(encoded, "+/-_") {
				t.Fatal("fixture does not distinguish the Base64 alphabets")
			}
			if err := refresh(http.StatusOK, encoded[:30]+"\n"+encoded[30:]); err != nil {
				t.Fatal(err)
			}
			i, j := a.state.Find(first.ID), a.state.Find(second.ID)
			if len(a.state.Servers) != 2 || i < 0 || j < 0 ||
				a.state.Servers[i].Profile.Name != "Renamed by feed" ||
				a.state.Servers[j].Profile.Name != "Second node" || a.state.Active != second.ID ||
				runtime.id != second.ID || runtime.starts != 1 || runtime.stops != 0 {
				t.Fatal("encoded refresh changed catalogue identity or restarted the running profile")
			}
		})
	}

	before, err := a.store.Load()
	if err != nil {
		t.Fatal(err)
	}
	for _, tc := range []reply{
		{status: http.StatusServiceUnavailable, body: "unavailable"},
		{status: http.StatusOK, body: raw + "\ninvalid-feed-line"},
	} {
		t.Run(fmt.Sprintf("failed refresh %d", tc.status), func(t *testing.T) {
			if err := refresh(tc.status, tc.body); err == nil {
				t.Fatal("failed refresh was accepted")
			}
			saved, err := a.store.Load()
			if err != nil || !reflect.DeepEqual(before, saved) || a.state.Active != second.ID ||
				runtime.id != second.ID || runtime.stops != 0 {
				t.Fatalf("failed refresh changed durable state or stopped the active profile: %v", err)
			}
		})
	}
	if err := runAction(action{Kind: "subscription-delete", ID: sub}); err != nil {
		t.Fatal(err)
	}
	saved, err := a.store.Load()
	if err != nil || len(saved.Subscriptions) != 0 || len(saved.Servers) != 0 ||
		saved.Active != "" || runtime.Running() || runtime.stops != 1 {
		t.Fatalf("removing the sole subscription did not withdraw the active profile: %v", err)
	}
	if got := requests.Load(); got != 7 {
		t.Fatalf("subscription URI received %d HTTPS requests, want 7", got)
	}
}

func TestParseProfilesEncodedEmptySubscription(t *testing.T) {
	for _, text := range []string{"[]", "\ufeff \r\n [] \r\n"} {
		encoded := base64.StdEncoding.EncodeToString([]byte(text))
		if profiles, err := parseProfiles([]byte(encoded), true); err != nil || len(profiles) != 0 {
			t.Fatalf("explicit encoded empty subscription was rejected: %v", err)
		}
		if _, err := parseProfiles([]byte(encoded), false); err == nil {
			t.Fatal("empty subscription marker was accepted by manual import")
		}
	}
	for _, text := range []string{" ", "\ufeff\r\n", "<html>not a feed</html>"} {
		encoded := base64.StdEncoding.EncodeToString([]byte(text))
		if _, err := parseProfiles([]byte(encoded), true); err == nil {
			t.Fatal("invalid encoded feed was accepted as an authoritative empty snapshot")
		}
	}
}
