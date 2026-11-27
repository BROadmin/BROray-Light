package lightapp

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/BROadmin/broray-light/internal/lightkeenetic"
	"github.com/BROadmin/broray-light/internal/lightstate"
	"github.com/BROadmin/broray-light/modules/servers"
	"github.com/BROadmin/broray-light/web/light"
)

type fakeRuntime struct {
	id            string
	starts, stops int
	probeErr      error
	failureID     string
}

func (r *fakeRuntime) Running() bool { return r.id != "" }
func (r *fakeRuntime) Stop() error {
	if r.id != "" {
		r.stops++
	}
	r.id = ""
	return nil
}
func (r *fakeRuntime) Start(_ context.Context, s servers.Server) error {
	r.starts++
	r.id = s.ID
	return nil
}
func (r *fakeRuntime) Check(context.Context, servers.Server) error { return r.probeErr }
func (r *fakeRuntime) Probe(context.Context) error {
	if r.id == r.failureID && r.failureID != "" {
		return errors.New("fixture active probe failed")
	}
	return r.probeErr
}

type fakeRouter struct {
	cleanupErr, readyErr error
	down                 bool
	webUpdates           int
	webListen            string
	webEnabled           bool
}

func (*fakeRouter) Authenticate(_ context.Context, user, pass string) error {
	if user == "fixture" && pass == "fixture" {
		return nil
	}
	return errors.New("invalid auth")
}
func (*fakeRouter) Ensure(context.Context, string) error  { return nil }
func (r *fakeRouter) Ready(context.Context, string) error { return r.readyErr }
func (r *fakeRouter) Cleanup(context.Context) error       { return r.cleanupErr }
func (r *fakeRouter) WAN(context.Context) (bool, bool)    { return true, !r.down }
func (r *fakeRouter) RemoteAccess(context.Context, string) (lightkeenetic.WebAccess, error) {
	if r.webEnabled {
		return lightkeenetic.WebAccess{State: "enabled", URL: "https://brolight.router.example/"}, nil
	}
	return lightkeenetic.WebAccess{State: "disabled"}, nil
}
func (r *fakeRouter) SetRemoteAccess(ctx context.Context, listen string, enabled bool) (lightkeenetic.WebAccess, error) {
	r.webUpdates++
	r.webListen, r.webEnabled = listen, enabled
	return r.RemoteAccess(ctx, listen)
}

const profile = "vless://11111111-1111-4111-8111-111111111111@node.example:443?security=reality&sni=old.example&pbk=R4NdomBase64UrlEncodedPublicKeyA1b2c3d4e5f6&sid=abcd#Original"

func newTestApp(t *testing.T) (*App, *fakeRuntime, *fakeRouter) {
	t.Helper()
	dir := t.TempDir()
	rt, router := &fakeRuntime{}, &fakeRouter{}
	app, err := New(filepath.Join(dir, "broray-light"), filepath.Join(dir, "run"), "127.0.0.1:1089", rt, router)
	if err != nil {
		t.Fatal(err)
	}
	return app, rt, router
}

func parse(t *testing.T, text string) []servers.Server {
	t.Helper()
	p, err := parseProfiles([]byte(text), false)
	if err != nil {
		t.Fatal(err)
	}
	return p
}

func seed(t *testing.T, a *App, profiles []servers.Server, sub string) string {
	t.Helper()
	s := a.state.Clone()
	if sub == "" {
		s.ImportManual(profiles)
	} else {
		s.Refresh(sub, profiles)
	}
	s.Active = s.Servers[0].Profile.ID
	if _, err := a.save(s); err != nil {
		t.Fatal(err)
	}
	return s.Active
}

func TestBootProbeFailurePreservesSelection(t *testing.T) {
	a, rt, _ := newTestApp(t)
	id := seed(t, a, parse(t, profile), "")
	rt.probeErr = errors.New("transient failure")
	a.tick(context.Background())
	saved, err := a.store.Load()
	if err != nil || saved.Active != id || a.state.Active != id || rt.Running() {
		t.Fatalf("intent/runtime mismatch after failing probe: %v", err)
	}
	if err := a.ready(context.Background()); err == nil {
		t.Fatal("update would commit before readiness")
	}
	rt.probeErr = nil
	a.tick(context.Background())
	if err := a.ready(context.Background()); err != nil || rt.id != id || rt.starts != 2 {
		t.Fatalf("boot recovery: %v", err)
	}
}

func TestSubscriptionRotationAndConfirmedWithdrawal(t *testing.T) {
	a, rt, _ := newTestApp(t)
	var body atomic.Value
	body.Store(profile)
	url := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, body.Load().(string)) }))
	defer url.Close()
	const sub = "sub-fixture"
	a.state.Subscriptions = []lightstate.Subscription{{ID: sub, URL: url.URL, Name: "Subscription"}}
	id := seed(t, a, parse(t, profile), sub)
	if err := a.restore(context.Background()); err != nil {
		t.Fatal(err)
	}

	body.Store("not a node")
	if err := a.refresh(context.Background(), sub); err == nil || rt.id != id || a.state.Active != id {
		t.Fatal("malformed response was treated as an authoritative snapshot")
	}
	body.Store("vless://11111111-1111-4111-8111-111111111111@node.example:443?security=reality&sni=new.example&pbk=R4NdomBase64UrlEncodedPublicKeyA1b2c3d4e5f6&sid=abcd#Rotated")
	if err := a.refresh(context.Background(), sub); err != nil {
		t.Fatal(err)
	}
	if a.state.Active != id || rt.id != id || rt.starts != 1 || !a.view().Servers[0].Pending {
		t.Fatal("rotation restarted Xray or substituted identity")
	}
	body.Store("[]")
	if err := a.refresh(context.Background(), sub); err != nil {
		t.Fatal(err)
	}
	saved, err := a.store.Load()
	if err != nil || saved.Active != "" || rt.Running() || a.state.Find(id) >= 0 || rt.stops != 1 {
		t.Fatalf("stale active after confirmed withdrawal: %v", err)
	}
}

func TestDuplicateManualAndSubscriptionsSurviveSourceRemoval(t *testing.T) {
	a, _, _ := newTestApp(t)
	profiles := parse(t, profile)
	id := seed(t, a, profiles, "")
	next := a.state.Clone()
	next.Refresh("sub-one", append(profiles, profiles...))
	next.Refresh("sub-two", profiles)
	if len(next.Servers) != 1 || len(next.Servers[0].Sources) != 2 || next.Servers[0].Profile.ID != id {
		t.Fatal("duplicate escaped canonical identity")
	}
	next.Refresh("sub-one", nil)
	next.Refresh("sub-two", nil)
	if len(next.Servers) != 1 || next.Servers[0].Profile.ID != id {
		t.Fatal("withdrawal deleted a manually retained profile")
	}
}

func TestReadinessAndCleanupRetry(t *testing.T) {
	a, rt, r := newTestApp(t)
	id := seed(t, a, parse(t, profile), "")
	a.state.ManageInterface = true
	if err := a.restore(context.Background()); err != nil {
		t.Fatal(err)
	}
	rt.probeErr = errors.New("transport unavailable")
	if err := a.ready(context.Background()); err == nil {
		t.Fatal("listener without traffic passed")
	}
	rt.probeErr = nil
	r.readyErr = errors.New("interface down")
	if err := a.ready(context.Background()); err == nil {
		t.Fatal("unready owned interface passed")
	}
	r.readyErr = nil
	if err := a.ready(context.Background()); err != nil || a.runningID != id {
		t.Fatalf("healthy installation rejected: %v", err)
	}
	r.cleanupErr = errors.New("native delete failed")
	if err := a.setInterface(context.Background(), false); err == nil {
		t.Fatal("cleanup reported success")
	}
	saved, err := a.store.Load()
	if err != nil || !saved.InterfaceCleanupPending {
		t.Fatalf("cleanup intent lost: %v", err)
	}
	r.cleanupErr = nil
	a.tick(context.Background())
	if a.state.InterfaceCleanupPending || !rt.Running() {
		t.Fatal("cleanup retry did not converge")
	}
}

func TestFullConflictAndWebUIAccess(t *testing.T) {
	a, _, _ := newTestApp(t)
	handler := a.Handler(light.Assets, "192.168.1.1:8080")
	for _, path := range []string{"/", "/servers", "/subscriptions", "/assets/light.js", "/assets/light.css"} {
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, httptest.NewRequest("GET", path, nil))
		if w.Code != 200 {
			t.Fatalf("asset %s status %d", path, w.Code)
		}
	}
	for _, path := range []string{"/routes", "/dot", "/api/ready", "/identity"} {
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, httptest.NewRequest("GET", path, nil))
		if w.Code != 404 {
			t.Fatalf("excluded route %s status %d", path, w.Code)
		}
	}
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, httptest.NewRequest("GET", "/api/state", nil))
	if w.Code != 401 {
		t.Fatal("unauthenticated state exposed")
	}
	post := func(path, body, csrf string, cookie *http.Cookie) *httptest.ResponseRecorder {
		req := httptest.NewRequest("POST", path, bytes.NewBufferString(body))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-CSRF-Token", csrf)
		if cookie != nil {
			req.AddCookie(cookie)
		}
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, req)
		return w
	}
	login := post("/api/login", `{"user":"fixture","password":"fixture"}`, "", nil)
	if login.Code != 200 || len(login.Result().Cookies()) != 1 {
		t.Fatalf("login status %d", login.Code)
	}
	cookie := login.Result().Cookies()[0]
	if cookie.Name != "BRORAY_LIGHT_SESSION" || !cookie.HttpOnly {
		t.Fatal("cookie is not isolated")
	}
	var payload map[string]string
	if err := json.Unmarshal(login.Body.Bytes(), &payload); err != nil {
		t.Fatal(err)
	}
	action := `{"kind":"import","text":"` + profile + `"}`
	if got := post("/api/action", action, "", cookie); got.Code != 403 {
		t.Fatalf("mutation without CSRF %d", got.Code)
	}
	if got := post("/api/action", action, payload["csrf"], cookie); got.Code != 200 {
		t.Fatalf("authenticated action %d %s", got.Code, got.Body)
	}
	if err := os.Mkdir(filepath.Join(filepath.Dir(a.root), "broray"), 0700); err != nil {
		t.Fatal(err)
	}
	if got := post("/api/action", action, payload["csrf"], cookie); got.Code == 200 {
		t.Fatal("mutation accepted alongside full BROray")
	}
}

func TestRemoteWebAccessRequiresSessionAndCSRF(t *testing.T) {
	app, _, router := newTestApp(t)
	const listener = "192.168.1.1:8080"
	handler := app.Handler(light.Assets, listener)
	send := func(method, path, data, csrf string, cookie *http.Cookie) *httptest.ResponseRecorder {
		req := httptest.NewRequest(method, path, strings.NewReader(data))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-CSRF-Token", csrf)
		if cookie != nil {
			req.AddCookie(cookie)
		}
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, req)
		return w
	}
	assert := func(w *httptest.ResponseRecorder, code int, state string) {
		t.Helper()
		if w.Code != code {
			t.Fatalf("HTTP %d, want %d: %s", w.Code, code, w.Body)
		}
		if state != "" {
			var out lightkeenetic.WebAccess
			if err := json.Unmarshal(w.Body.Bytes(), &out); err != nil || out.State != state {
				t.Fatalf("state %q, want %q: %s (%v)", out.State, state, w.Body, err)
			}
			if state == "enabled" && out.URL != "https://brolight.router.example/" || state == "disabled" && out.URL != "" {
				t.Fatalf("unexpected publication URL: %q", out.URL)
			}
		}
	}
	const path = "/api/web-access"
	assert(send("GET", path, "", "", nil), 401, "")
	assert(send("POST", path, `{"enabled":true}`, "", nil), 401, "")

	credentials := `{"user":"fixture","password":"fixture"}`
	lanLogin := send("POST", "http://"+listener+"/api/login", credentials, "", nil)
	assert(lanLogin, 200, "")
	if cookies := lanLogin.Result().Cookies(); len(cookies) != 1 || cookies[0].Secure {
		t.Fatalf("expected login cookie usable over LAN HTTP: %v", cookies)
	}
	// The observed KeenDNS proxy rewrites Host to the LAN endpoint and removes
	// Origin and TLS metadata. The HTTPS client can still require Secure.
	forwarded := send("POST", "http://"+listener+"/api/login",
		`{"user":"fixture","password":"fixture","secureSession":true}`, "", nil)
	assert(forwarded, 200, "")
	if cookies := forwarded.Result().Cookies(); len(cookies) != 1 || !cookies[0].Secure {
		t.Fatalf("HTTPS client lost Secure after proxy rewrote headers: %v", cookies)
	}
	remote := "http://brolight.router.example"
	remoteLogin := send("POST", remote+"/api/login", credentials, "", nil)
	assert(remoteLogin, 200, "")
	cookies := remoteLogin.Result().Cookies()
	if len(cookies) != 1 || !cookies[0].Secure || !cookies[0].HttpOnly || cookies[0].Domain != "" || cookies[0].SameSite != http.SameSiteStrictMode {
		t.Fatalf("unexpected cookie behind TLS proxy: %v", cookies)
	}
	var authenticated map[string]string
	if err := json.Unmarshal(remoteLogin.Body.Bytes(), &authenticated); err != nil || authenticated["csrf"] == "" {
		t.Fatalf("login did not provide CSRF token: %v", err)
	}
	csrf, cookie := authenticated["csrf"], cookies[0]
	assert(send("GET", path, "", "", cookie), 200, "disabled")
	assert(send("POST", path, `{"enabled":true}`, "", cookie), 403, "")
	assert(send("POST", path, `{}`, csrf, cookie), 400, "")
	if router.webUpdates != 0 {
		t.Fatal("reading status or an invalid mutation changed the publication")
	}
	assert(send("POST", path, `{"enabled":true}`, csrf, cookie), 200, "enabled")
	if router.webUpdates != 1 || router.webListen != listener {
		t.Fatalf("expected one update for bound listener %s", listener)
	}
	assert(send("GET", path, "", "", cookie), 200, "enabled")
	assert(send("POST", path, `{"enabled":false}`, csrf, cookie), 200, "disabled")
	if router.webUpdates != 2 {
		t.Fatal("authenticated disable did not update the publication")
	}
	assert(send("POST", remote+"/api/logout", "", csrf, cookie), 200, "")
	assert(send("GET", path, "", "", cookie), 401, "")
}

func TestPendingInterfaceCleanupDoesNotPreventProxyRestore(t *testing.T) {
	a, rt, router := newTestApp(t)
	id := seed(t, a, parse(t, profile), "")
	router.cleanupErr = errors.New("owned interface still referenced")
	next := a.state.Clone()
	next.InterfaceCleanupPending = true
	if _, err := a.save(next); err != nil {
		t.Fatal(err)
	}

	a.tick(context.Background())
	if !rt.Running() || a.runningID != id || a.health != router.cleanupErr.Error() {
		t.Fatalf("running=%v selected=%q health=%q", rt.Running(), a.runningID, a.health)
	}
	req := httptest.NewRequest("POST", "/api/action", strings.NewReader(`{"kind":"update-apply"}`))
	req.Header.Set("Content-Type", "application/json")
	_, err := a.action(httptest.NewRecorder(), req)
	if err == nil || !strings.Contains(err.Error(), "Keenetic cleanup is pending") {
		t.Fatalf("update admission error = %v", err)
	}

	query := url.Values{"version": {Version}, "root": {a.root}}
	handler := a.ControlHandler()
	for _, tc := range []struct {
		path string
		code int
	}{
		{"/ready?" + query.Encode(), 503},
		{"/identity?" + query.Encode(), 200},
		{"/identity?root=" + url.QueryEscape(a.root), 409},
		{"/identity?version=" + url.QueryEscape(Version), 409},
	} {
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, httptest.NewRequest("GET", tc.path, nil))
		if w.Code != tc.code {
			t.Errorf("%s status = %d, want %d", tc.path, w.Code, tc.code)
		}
	}
}

func TestFailoverWaitsForWANThresholdAndCooldown(t *testing.T) {
	a, rt, router := newTestApp(t)
	p := parse(t, profile)[0]
	first, second := p, p
	first.Address, second.Address = "first.example", "second.example"
	id := seed(t, a, []servers.Server{p, first, second}, "")
	a.state.Failover = lightstate.Failover{Enabled: true, Threshold: 2, CooldownSeconds: 30}
	if err := a.restore(context.Background()); err != nil {
		t.Fatal(err)
	}
	rt.failureID = id
	router.down = true
	a.tick(context.Background())
	a.tick(context.Background())
	if a.state.Active != id || a.failures != 0 {
		t.Fatal("confirmed WAN loss consumed a failover")
	}
	router.down = false
	a.tick(context.Background())
	if a.state.Active != id || a.failures != 1 {
		t.Fatal("threshold was not respected")
	}
	a.nextSwitch = time.Now().Add(time.Minute)
	a.tick(context.Background())
	if a.state.Active != id {
		t.Fatal("cooldown was not respected")
	}
	a.nextSwitch = time.Time{}
	a.tick(context.Background())
	if a.state.Active != a.state.Servers[1].Profile.ID || rt.id != a.state.Active {
		t.Fatal("first candidate in the configured order was not activated")
	}
}
