package lightapp

import (
	"bytes"
	"context"
	"encoding/base64"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"slices"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/BROadmin/broray-light/internal/lightinstall"
	"github.com/BROadmin/broray-light/internal/lightstate"
	"github.com/BROadmin/broray-light/modules/servers"
)

const importLimit = 2 << 20

func trimSubscriptionBody(data []byte) []byte {
	return bytes.TrimSpace(bytes.TrimPrefix(bytes.TrimSpace(data), []byte{0xef, 0xbb, 0xbf}))
}

func parseProfiles(data []byte, allowEmpty bool) ([]servers.Server, error) {
	data = trimSubscriptionBody(data)
	if len(data) == 0 || len(data) > importLimit || !utf8.Valid(data) {
		return nil, errors.New("empty, too large or invalid UTF-8 server list")
	}
	if !bytes.Contains(data, []byte("://")) {
		base := strings.Join(strings.Fields(string(data)), "")
		for _, decoder := range []*base64.Encoding{base64.StdEncoding, base64.RawStdEncoding, base64.URLEncoding, base64.RawURLEncoding} {
			decoded, err := decoder.DecodeString(base)
			decoded = trimSubscriptionBody(decoded)
			if err == nil && utf8.Valid(decoded) && (bytes.Contains(decoded, []byte("://")) || allowEmpty && bytes.Equal(decoded, []byte("[]"))) {
				data = decoded
				break
			}
		}
	}
	if allowEmpty && bytes.Equal(data, []byte("[]")) {
		return nil, nil
	}
	var profiles []servers.Server
	for i, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		profile, err := servers.ParseLink(line)
		if err != nil {
			return nil, fmt.Errorf("invalid or unsupported server on line %d", i+1)
		}
		if len(profiles) == 2048 {
			return nil, errors.New("server list exceeds 2048 entries")
		}
		profiles = append(profiles, profile)
	}
	if len(profiles) == 0 {
		return nil, errors.New("server list contains no valid nodes")
	}
	return profiles, nil
}

func subscriptionURL(raw string) (string, error) {
	u, err := url.Parse(strings.TrimSpace(raw))
	if err != nil || u.Hostname() == "" || (u.Scheme != "http" && u.Scheme != "https") || u.Fragment != "" || u.User != nil || len(raw) > 8192 {
		return "", errors.New("provide an HTTP or HTTPS subscription URL")
	}
	u.Host = strings.ToLower(u.Host)
	if u.Path == "" {
		u.Path = "/"
	}
	return u.String(), nil
}

var subscriptionHTTP = &http.Client{
	Timeout: 18 * time.Second,
	Transport: &http.Transport{
		DialContext:           (&net.Dialer{Timeout: 7 * time.Second}).DialContext,
		TLSHandshakeTimeout:   7 * time.Second,
		ResponseHeaderTimeout: 10 * time.Second,
	},
	CheckRedirect: func(req *http.Request, via []*http.Request) error {
		if len(via) >= 4 || (via[0].URL.Scheme == "https" && req.URL.Scheme != "https") {
			return errors.New("subscription redirect rejected")
		}
		_, err := subscriptionURL(req.URL.String())
		return err
	},
}

func fetchProfiles(ctx context.Context, raw string) ([]servers.Server, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, raw, nil)
	if err != nil {
		return nil, errors.New("subscription URL rejected")
	}
	req.Header.Set("User-Agent", "BROray-Light/"+Version)
	response, err := subscriptionHTTP.Do(req)
	if err != nil {
		return nil, errors.New("subscription download failed")
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("subscription returned HTTP %d", response.StatusCode)
	}
	data, err := io.ReadAll(io.LimitReader(response.Body, importLimit+1))
	if err != nil || len(data) > importLimit {
		return nil, errors.New("subscription is unreadable or too large")
	}
	return parseProfiles(data, true)
}

func (a *App) refresh(ctx context.Context, id string) error {
	a.mu.Lock()
	i := a.state.FindSubscription(id)
	if i < 0 {
		a.mu.Unlock()
		return errors.New("unknown subscription")
	}
	original := a.state.Subscriptions[i]
	a.mu.Unlock()

	profiles, err := fetchProfiles(ctx, original.URL)
	if err != nil {
		return err
	}

	a.mu.Lock()
	defer a.mu.Unlock()
	if ctx.Err() != nil {
		return ctx.Err()
	}
	if err := NoFullProduct(a.root); err != nil {
		return err
	}
	if lightinstall.Pending(a.root) {
		return errors.New("installation is awaiting confirmation")
	}
	next := a.state.Clone()
	i = next.FindSubscription(id)
	if i < 0 || next.Subscriptions[i] != original {
		return errors.New("subscription changed while downloading; refresh it again")
	}
	next.Subscriptions[i].RefreshedAt = time.Now().UTC()
	next.Refresh(id, profiles)
	if len(next.Servers) > 4096 {
		return errors.New("catalogue exceeds 4096 servers")
	}
	return a.reconcileSubscription(ctx, next)
}

func (a *App) refreshDue(ctx context.Context) {
	if lightinstall.Pending(a.root) {
		return
	}
	a.mu.Lock()
	var id string
	for _, sub := range a.state.Subscriptions {
		if sub.RefreshMinutes > 0 && time.Since(sub.RefreshedAt) >= time.Duration(sub.RefreshMinutes)*time.Minute {
			// Rotate on failures too, without modifying durable last-success evidence.
			if _, ok := a.refreshAttempts[sub.ID]; !ok || time.Since(a.refreshAttempts[sub.ID]) >= time.Minute {
				id = sub.ID
				a.refreshAttempts[id] = time.Now()
				break
			}
		}
	}
	a.mu.Unlock()
	if id != "" {
		_ = a.refresh(ctx, id)
	}
}

func (a *App) setSubscription(ctx context.Context, id, name, raw string, minutes int, remove bool) error {
	next := a.state.Clone()
	i := next.FindSubscription(id)
	if remove {
		if i < 0 {
			return errors.New("unknown subscription")
		}
		delete(a.refreshAttempts, id)
		next.Subscriptions = slices.Delete(next.Subscriptions, i, i+1)
		next.Refresh(id, nil)
		return a.reconcileSubscription(ctx, next)
	}
	if len(name) > 120 || minutes < 0 || minutes > 10080 || (minutes != 0 && minutes < 5) {
		return errors.New("invalid subscription name or refresh interval (5–10080 minutes, or 0 for manual refresh)")
	}
	canonical, err := subscriptionURL(raw)
	if err != nil {
		return err
	}
	if slices.ContainsFunc(next.Subscriptions, func(s lightstate.Subscription) bool { return s.URL == canonical && s.ID != id }) {
		return errors.New("subscription URL already exists")
	}
	if name == "" {
		name = "Subscription"
	}
	if id == "" {
		next.Subscriptions = append(next.Subscriptions, lightstate.Subscription{ID: servers.NewID(), Name: name, URL: canonical, RefreshMinutes: minutes})
	} else {
		if i < 0 {
			return errors.New("unknown subscription")
		}
		next.Subscriptions[i].Name = name
		next.Subscriptions[i].RefreshMinutes = minutes
		if next.Subscriptions[i].URL != canonical {
			// Keep the old validated snapshot until a successful fetch of the new URL.
			next.Subscriptions[i].RefreshedAt = time.Time{}
			next.Subscriptions[i].URL = canonical
		}
	}
	_, err = a.save(next)
	return err
}
