package lightapp

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"net"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/BROadmin/broray-light/internal/lightinstall"
	"github.com/BROadmin/broray-light/internal/lightstate"
	"github.com/BROadmin/broray-light/internal/session"
	"github.com/BROadmin/broray-light/modules/servers"
)

type serverView struct {
	servers.Summary
	ServerName    string `json:"serverName,omitempty"`
	Flow          string `json:"flow,omitempty"`
	TransportHost string `json:"transportHost,omitempty"`
	Path          string `json:"path,omitempty"`
	ServiceName   string `json:"serviceName,omitempty"`
	Excluded      bool   `json:"excluded"`
	Pending       bool   `json:"pending"`
}

type stateView struct {
	Version         string                    `json:"version"`
	Active          string                    `json:"active"`
	Running         bool                      `json:"running"`
	Health          string                    `json:"health"`
	ManageInterface bool                      `json:"manageInterface"`
	CleanupPending  bool                      `json:"cleanupPending"`
	Failover        lightstate.Failover       `json:"failover"`
	Servers         []serverView              `json:"servers"`
	Subscriptions   []lightstate.Subscription `json:"subscriptions"`
}

func (a *App) view() stateView {
	a.mu.Lock()
	defer a.mu.Unlock()
	v := stateView{
		Version: Version, Active: a.state.Active, Running: a.runtime.Running(), Health: a.health,
		ManageInterface: a.state.ManageInterface, CleanupPending: a.state.InterfaceCleanupPending,
		Failover: a.state.Failover, Servers: make([]serverView, 0, len(a.state.Servers)),
		Subscriptions: a.state.Clone().Subscriptions,
	}
	for _, entry := range a.state.Servers {
		active := entry.Profile.ID == a.state.Active
		profile := entry.Profile
		serverName := profile.TLS.ServerName
		if profile.Security == "reality" {
			serverName = profile.Reality.ServerName
		}
		v.Servers = append(v.Servers, serverView{Summary: profile.Summary(active), Excluded: entry.Excluded,
			Pending:    active && a.runningID == profile.ID && a.runningKey != lightstate.ProfileKey(profile),
			ServerName: serverName, Flow: profile.Flow, TransportHost: profile.Transport.Host,
			Path: profile.Transport.Path, ServiceName: profile.Transport.ServiceName})
	}
	return v
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

func readJSON(w http.ResponseWriter, r *http.Request, dst any) error {
	contentType := strings.TrimSpace(strings.Split(r.Header.Get("Content-Type"), ";")[0])
	if contentType != "application/json" {
		return errors.New("expected application/json")
	}
	r.Body = http.MaxBytesReader(w, r.Body, 3<<20)
	d := json.NewDecoder(r.Body)
	d.DisallowUnknownFields()
	if err := d.Decode(dst); err != nil || d.Decode(&struct{}{}) != io.EOF {
		return errors.New("invalid JSON request")
	}
	return nil
}

type action struct {
	Kind           string              `json:"kind"`
	ID             string              `json:"id"`
	Name           string              `json:"name"`
	Position       int                 `json:"position"`
	Enabled        bool                `json:"enabled"`
	Text           string              `json:"text"`
	URL            string              `json:"url"`
	RefreshMinutes int                 `json:"refreshMinutes"`
	Failover       lightstate.Failover `json:"failover"`
}

func (a *App) action(w http.ResponseWriter, r *http.Request) (any, error) {
	var input action
	if err := readJSON(w, r, &input); err != nil {
		return nil, err
	}
	ctx := r.Context()
	switch input.Kind {
	case "subscription-refresh":
		return nil, a.refresh(ctx, input.ID)
	case "update-check":
		return lightinstall.Check(ctx)
	}
	a.mu.Lock()
	defer a.mu.Unlock()
	if ctx.Err() != nil {
		return nil, ctx.Err()
	}
	if err := NoFullProduct(a.root); err != nil {
		return nil, err
	}
	if lightinstall.Pending(a.root) {
		return nil, errors.New("installation is awaiting confirmation")
	}
	switch input.Kind {
	case "activate":
		return nil, a.activate(ctx, input.ID)
	case "check":
		i := a.state.Find(input.ID)
		if i < 0 {
			return nil, errors.New("unknown server")
		}
		return nil, a.runtime.Check(ctx, a.state.Servers[i].Profile)
	case "rename", "move", "exclude", "delete":
		return nil, a.changeServer(ctx, input.ID, input.Kind, strings.TrimSpace(input.Name), input.Position, input.Enabled)
	case "import":
		profiles, err := parseProfiles([]byte(input.Text), false)
		if err != nil {
			return nil, err
		}
		next := a.state.Clone()
		added := next.ImportManual(profiles)
		if len(next.Servers) > 4096 {
			return nil, errors.New("catalogue exceeds 4096 servers")
		}
		_, err = a.save(next)
		return map[string]int{"added": added}, err
	case "subscription-save", "subscription-delete":
		return nil, a.setSubscription(ctx, input.ID, strings.TrimSpace(input.Name), input.URL, input.RefreshMinutes, input.Kind == "subscription-delete")
	case "interface":
		return nil, a.setInterface(ctx, input.Enabled)
	case "failover":
		if input.Failover.Threshold < 1 || input.Failover.Threshold > 20 || input.Failover.CooldownSeconds < 15 || input.Failover.CooldownSeconds > 3600 {
			return nil, errors.New("failover threshold must be 1–20 and cooldown 15–3600 seconds")
		}
		next := a.state.Clone()
		next.Failover = input.Failover
		_, err := a.save(next)
		return nil, err
	case "core-check", "core-install":
		return a.core(ctx, input.Kind == "core-install")
	case "update-apply":
		if err := a.readyLocked(ctx); err != nil {
			return nil, fmt.Errorf("current service is not ready for update: %w", err)
		}
		return nil, lightinstall.Launch(ctx, a.root, a.run)
	default:
		return nil, errors.New("unknown operation")
	}
}

type loginLimit struct {
	mu       sync.Mutex
	attempts map[string]attempt
}
type attempt struct {
	stamp time.Time
	count int
}

func (l *loginLimit) allow(peer string) bool {
	ip, _, err := net.SplitHostPort(peer)
	if err != nil {
		ip = peer
	}
	l.mu.Lock()
	defer l.mu.Unlock()
	now := time.Now()
	for key, prior := range l.attempts {
		if now.Sub(prior.stamp) >= time.Minute {
			delete(l.attempts, key)
		}
	}
	prior, exists := l.attempts[ip]
	if len(l.attempts) >= 256 && !exists {
		return false
	}
	if !exists {
		prior.stamp = now
	}
	if prior.count >= 10 {
		return false
	}
	prior.count++
	l.attempts[ip] = prior
	return true
}

func (a *App) Handler(assets fs.FS) http.Handler {
	sessions := session.NewStore()
	limits := loginLimit{attempts: make(map[string]attempt)}
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/login", func(w http.ResponseWriter, r *http.Request) {
		var creds struct {
			User     string `json:"user"`
			Password string `json:"password"`
		}
		if err := readJSON(w, r, &creds); err != nil || creds.User == "" || len(creds.User) > 128 || creds.Password == "" || len(creds.Password) > 256 {
			writeJSON(w, 400, map[string]string{"error": "invalid login fields"})
			return
		}
		if !limits.allow(r.RemoteAddr) {
			w.Header().Set("Retry-After", "60")
			writeJSON(w, 429, map[string]string{"error": "too many login attempts"})
			return
		}
		if a.router.Authenticate(r.Context(), creds.User, creds.Password) != nil {
			writeJSON(w, 401, map[string]string{"error": "Keenetic authentication failed"})
			return
		}
		token, view, err := sessions.Create(creds.User)
		if err != nil {
			writeJSON(w, 503, map[string]string{"error": "session unavailable"})
			return
		}
		http.SetCookie(w, &http.Cookie{Name: session.CookieName, Value: token, Path: "/", HttpOnly: true, Secure: r.TLS != nil, SameSite: http.SameSiteStrictMode})
		writeJSON(w, 200, map[string]string{"csrf": view.CSRF})
	})
	requireSession := func(mutate bool, handler func(http.ResponseWriter, *http.Request, *http.Cookie, session.View)) http.HandlerFunc {
		return func(w http.ResponseWriter, r *http.Request) {
			cookie, err := r.Cookie(session.CookieName)
			if err == nil {
				view, ok := sessions.Lookup(cookie.Value)
				if ok {
					if mutate && !session.ValidCSRF(view, r.Header.Get("X-CSRF-Token")) {
						writeJSON(w, 403, map[string]string{"error": "invalid CSRF token"})
						return
					}
					handler(w, r, cookie, view)
					return
				}
			}
			writeJSON(w, 401, map[string]string{"error": "sign in to Keenetic"})
		}
	}
	mux.HandleFunc("GET /api/state", requireSession(false, func(w http.ResponseWriter, r *http.Request, _ *http.Cookie, v session.View) {
		writeJSON(w, 200, map[string]any{"csrf": v.CSRF, "state": a.view()})
	}))
	mux.HandleFunc("POST /api/action", requireSession(true, func(w http.ResponseWriter, r *http.Request, _ *http.Cookie, _ session.View) {
		result, err := a.action(w, r)
		if err != nil {
			writeJSON(w, 400, map[string]string{"error": err.Error()})
			return
		}
		writeJSON(w, 200, map[string]any{"result": result})
	}))
	mux.HandleFunc("POST /api/logout", requireSession(true, func(w http.ResponseWriter, r *http.Request, c *http.Cookie, _ session.View) {
		sessions.Delete(c.Value)
		http.SetCookie(w, &http.Cookie{Name: session.CookieName, Path: "/", HttpOnly: true, Secure: r.TLS != nil, SameSite: http.SameSiteStrictMode, MaxAge: -1})
		writeJSON(w, 200, map[string]bool{"ok": true})
	}))
	mux.Handle("GET /assets/", http.FileServerFS(assets))
	for _, path := range []string{"/{$}", "/servers", "/subscriptions"} {
		mux.HandleFunc("GET "+path, func(w http.ResponseWriter, r *http.Request) {
			http.ServeFileFS(w, r, assets, "index.html")
		})
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("Referrer-Policy", "no-referrer")
		w.Header().Set("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'")
		mux.ServeHTTP(w, r)
	})
}

func (a *App) ControlHandler() http.Handler {
	mux := http.NewServeMux()
	control := func(w http.ResponseWriter, r *http.Request) {
		identityOnly := r.URL.Path == "/identity"
		root, version := r.URL.Query().Get("root"), r.URL.Query().Get("version")
		if (identityOnly || root != "") && root != a.root {
			writeJSON(w, 409, map[string]string{"error": "unexpected installation root"})
			return
		}
		if (identityOnly || version != "") && version != Version {
			writeJSON(w, 409, map[string]string{"error": "unexpected running version"})
			return
		}
		if !identityOnly {
			if err := a.ready(r.Context()); err != nil {
				writeJSON(w, 503, map[string]string{"error": err.Error()})
				return
			}
		}
		writeJSON(w, 200, map[string]string{"version": Version})
	}
	mux.HandleFunc("GET /ready", control)
	mux.HandleFunc("GET /identity", control)
	return mux
}
