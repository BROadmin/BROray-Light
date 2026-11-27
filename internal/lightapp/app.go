package lightapp

import (
	"context"
	"errors"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"slices"
	"sync"
	"time"

	"github.com/BROadmin/broray-light/internal/lightinstall"
	"github.com/BROadmin/broray-light/internal/lightkeenetic"
	"github.com/BROadmin/broray-light/internal/lightstate"
	"github.com/BROadmin/broray-light/modules/servers"
)

const Version = lightinstall.Version

type Runtime interface {
	Running() bool
	Stop() error
	Start(context.Context, servers.Server) error
	Check(context.Context, servers.Server) error
	Probe(context.Context) error
}

type Router interface {
	Authenticate(context.Context, string, string) error
	Ensure(context.Context, string) error
	Ready(context.Context, string) error
	Cleanup(context.Context) error
	WAN(context.Context) (known, online bool)
	RemoteAccess(context.Context, string) (lightkeenetic.WebAccess, error)
	SetRemoteAccess(context.Context, string, bool) (lightkeenetic.WebAccess, error)
}

type App struct {
	mu              sync.Mutex
	store           lightstate.Store
	state           lightstate.State
	runtime         Runtime
	router          Router
	root            string
	run             string
	socks           string
	runningID       string
	runningKey      string
	runningProfile  servers.Server
	readyOnce       bool
	failures        int
	nextSwitch      time.Time
	health          string
	refreshAttempts map[string]time.Time
}

func New(root, run, socks string, rt Runtime, router Router) (*App, error) {
	if err := NoFullProduct(root); err != nil {
		return nil, err
	}
	store := lightstate.NewStore(root)
	st, err := store.Load()
	if err != nil {
		return nil, err
	}
	if st.Active != "" {
		i := st.Find(st.Active)
		if i < 0 || st.Servers[i].Excluded {
			return nil, errors.New("selected server is absent or excluded in saved state")
		}
	}
	return &App{store: store, state: st, runtime: rt, router: router, root: root, run: run, socks: socks, refreshAttempts: make(map[string]time.Time)}, nil
}

func NoFullProduct(root string) error {
	base := filepath.Dir(root)
	for _, path := range []string{
		filepath.Join(base, "broray"),
		filepath.Join(base, "etc", "init.d", "S24broray"),
		filepath.Join(base, "etc", "init.d", "S22broray-updater"),
		filepath.Join(base, "bin", "broray-system"),
	} {
		if _, err := os.Lstat(path); err == nil {
			return errors.New("full BROray is installed; Light cannot use this router concurrently")
		} else if !errors.Is(err, os.ErrNotExist) {
			return err
		}
	}
	return nil
}

func (a *App) save(next lightstate.State) (bool, error) {
	committed, err := a.store.Save(next)
	if committed {
		a.state = next
	}
	return committed, err
}

func (a *App) stop() error {
	if err := a.runtime.Stop(); err != nil {
		return err
	}
	a.runningID, a.runningKey = "", ""
	a.runningProfile = servers.Server{}
	return nil
}

func (a *App) start(ctx context.Context, profile servers.Server) error {
	if err := a.stop(); err != nil {
		return err
	}
	if err := a.runtime.Start(ctx, profile); err != nil {
		return err
	}
	if err := a.runtime.Probe(ctx); err != nil {
		return errors.Join(err, a.stop())
	}
	if a.state.ManageInterface {
		if err := a.router.Ensure(ctx, a.socks); err != nil {
			return errors.Join(err, a.stop())
		}
	}
	a.runningID = profile.ID
	a.runningKey = lightstate.ProfileKey(profile)
	a.runningProfile = profile
	return nil
}

func (a *App) restore(ctx context.Context) error {
	if i := a.state.Find(a.state.Active); i >= 0 {
		if a.runningID == a.state.Active && a.runtime.Running() {
			return nil
		}
		if err := a.start(ctx, a.state.Servers[i].Profile); err != nil {
			return err
		}
		a.readyOnce = true
	}
	return nil
}

func (a *App) activate(ctx context.Context, id string) error {
	i := a.state.Find(id)
	if i < 0 || a.state.Servers[i].Excluded {
		return errors.New("server absent or excluded")
	}
	old := a.runningProfile
	if old.ID == "" {
		if previous := a.state.Find(a.state.Active); previous >= 0 {
			old = a.state.Servers[previous].Profile
		}
	}
	candidate := a.state.Servers[i].Profile
	if a.runningID == id && a.runningKey == lightstate.ProfileKey(candidate) && a.runtime.Running() {
		return a.runtime.Probe(ctx)
	}
	// Check a candidate in a separate SOCKS process before interrupting a
	// working connection. The real port is verified again after the switch.
	if a.runtime.Running() {
		if err := a.runtime.Check(ctx, candidate); err != nil {
			return err
		}
	}
	if err := a.start(ctx, candidate); err != nil {
		return errors.Join(err, a.restorePrevious(old))
	}
	next := a.state.Clone()
	next.Active = id
	committed, err := a.save(next)
	if !committed {
		return errors.Join(err, a.stop(), a.restorePrevious(old))
	}
	a.readyOnce = true
	a.failures = 0
	a.nextSwitch = time.Now().Add(time.Duration(a.state.Failover.CooldownSeconds) * time.Second)
	a.health = ""
	return err
}

func (a *App) restorePrevious(profile servers.Server) error {
	if profile.ID == "" {
		return nil
	}
	ctx, cancel := context.WithTimeout(context.Background(), 35*time.Second)
	defer cancel()
	return a.start(ctx, profile)
}

// Reconcile removes stale intent when a successful catalog transaction
// withdraws it. If another source still supplies the profile, it survives.
func (a *App) reconcile(ctx context.Context, next lightstate.State) error {
	retired := false
	if next.Active != "" {
		i := next.Find(next.Active)
		retired = i < 0 || next.Servers[i].Excluded
		if retired {
			next.Active = ""
		}
	}
	committed, saveErr := a.save(next)
	if !committed || !retired {
		return saveErr
	}
	a.readyOnce = false
	a.failures = 0
	if err := a.stop(); err != nil {
		return errors.Join(saveErr, err)
	}
	if a.state.Failover.Enabled {
		a.tryFailover(ctx)
	}
	return saveErr
}

func (a *App) tryFailover(ctx context.Context) {
	a.nextSwitch = time.Now().Add(time.Duration(a.state.Failover.CooldownSeconds) * time.Second)
	for _, entry := range a.state.Servers {
		if ctx.Err() != nil {
			return
		}
		if entry.Excluded || entry.Profile.ID == a.state.Active {
			continue
		}
		if err := a.activate(ctx, entry.Profile.ID); err == nil || a.state.Active == entry.Profile.ID {
			return
		}
	}
}

func (a *App) ready(ctx context.Context) error {
	a.mu.Lock()
	defer a.mu.Unlock()
	return a.readyLocked(ctx)
}

// readyLocked checks update admission with a.mu held.
func (a *App) readyLocked(ctx context.Context) error {
	if err := NoFullProduct(a.root); err != nil {
		return err
	}
	if a.state.InterfaceCleanupPending {
		return errors.New("Keenetic cleanup is pending")
	}
	if a.state.Active == "" {
		if a.runtime.Running() {
			return errors.New("unselected Xray is still running")
		}
		return nil
	}
	if a.runningID != a.state.Active || !a.runtime.Running() {
		return errors.New("selected Xray is not running")
	}
	if err := a.runtime.Probe(ctx); err != nil {
		return err
	}
	if a.state.ManageInterface {
		return a.router.Ready(ctx, a.socks)
	}
	return nil
}

func (a *App) setInterface(ctx context.Context, enabled bool) error {
	next := a.state.Clone()
	if enabled {
		if !a.runtime.Running() {
			return errors.New("activate a server before enabling the Keenetic interface")
		}
		if err := a.runtime.Probe(ctx); err != nil {
			return err
		}
		// Keep durable intent if native confirmation is interrupted.
		next.ManageInterface, next.InterfaceCleanupPending = true, false
		committed, err := a.save(next)
		if !committed {
			return err
		}
		return errors.Join(err, a.router.Ensure(ctx, a.socks))
	}
	next.ManageInterface, next.InterfaceCleanupPending = false, true
	committed, err := a.save(next)
	if !committed {
		return err
	}
	return errors.Join(err, a.cleanupInterface(ctx))
}

func (a *App) cleanupInterface(ctx context.Context) error {
	if err := a.router.Cleanup(ctx); err != nil {
		return err
	}
	next := a.state.Clone()
	next.InterfaceCleanupPending = false
	_, err := a.save(next)
	return err
}

func (a *App) tick(ctx context.Context) {
	a.mu.Lock()
	defer a.mu.Unlock()
	if err := NoFullProduct(a.root); err != nil {
		a.health = errors.Join(err, a.stop()).Error()
		return
	}
	a.health = ""
	var cleanupErr error
	if a.state.InterfaceCleanupPending {
		cleanupErr = a.cleanupInterface(ctx)
		if cleanupErr != nil {
			a.health = cleanupErr.Error()
		}
	}
	if a.state.Active == "" {
		if err := a.stop(); err != nil {
			a.health = errors.Join(cleanupErr, err).Error()
		}
		return
	}
	wasRunning := a.runtime.Running()
	err := a.restore(ctx)
	if err == nil && wasRunning {
		err = a.runtime.Probe(ctx)
		if err == nil && a.state.ManageInterface {
			if err := a.router.Ready(ctx, a.socks); err != nil {
				err = a.router.Ensure(ctx, a.socks)
				if err != nil {
					a.health = errors.Join(cleanupErr, err).Error()
					return
				}
			}
		}
	}
	if err == nil {
		a.failures = 0
		return
	}
	a.health = errors.Join(cleanupErr, err).Error()
	if !a.readyOnce || !a.state.Failover.Enabled || lightinstall.Pending(a.root) {
		return
	}
	if known, online := a.router.WAN(ctx); known && !online {
		a.failures = 0
		a.health = "WAN is unavailable; automatic switching is paused"
		return
	}
	a.failures++
	if a.failures >= a.state.Failover.Threshold && !time.Now().Before(a.nextSwitch) {
		a.tryFailover(ctx)
	}
}

func (a *App) Watch(ctx context.Context) {
	a.tick(ctx)
	tick := time.NewTicker(12 * time.Second)
	defer tick.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-tick.C:
			a.tick(ctx)
			a.refreshDue(ctx)
		}
	}
}

func (a *App) Close() {
	a.mu.Lock()
	defer a.mu.Unlock()
	if err := a.stop(); err != nil {
		log.Print(err)
	}
}

func (a *App) changeServer(ctx context.Context, id, action, name string, position int, excluded bool) error {
	next := a.state.Clone()
	i := next.Find(id)
	if i < 0 {
		return errors.New("unknown server")
	}
	switch action {
	case "rename":
		if len(name) == 0 || len(name) > 120 {
			return errors.New("provide a server name up to 120 bytes")
		}
		next.Servers[i].Profile.Name = name
		next.Servers[i].Renamed = true
	case "move":
		if position < 0 || position >= len(next.Servers) {
			return errors.New("invalid position")
		}
		item := next.Servers[i]
		next.Servers = slices.Delete(next.Servers, i, i+1)
		next.Servers = slices.Insert(next.Servers, position, item)
	case "exclude":
		next.Servers[i].Excluded = excluded
	case "delete":
		next.Servers = slices.Delete(next.Servers, i, i+1)
	default:
		return fmt.Errorf("unknown server operation")
	}
	return a.reconcile(ctx, next)
}
