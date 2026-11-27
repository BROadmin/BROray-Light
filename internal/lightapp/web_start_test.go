package lightapp

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/BROadmin/broray-light/internal/lightinstall"
	"github.com/BROadmin/broray-light/internal/lightkeenetic"
)

const webTestListener = "192.168.1.1:8080"

type publicationRouter struct {
	fakeRouter
	status  lightkeenetic.WebAccess
	err     error
	read    int
	writes  int
	inspect func()
	apply   func(context.Context)
}

func (r *publicationRouter) RemoteAccess(context.Context, string) (lightkeenetic.WebAccess, error) {
	r.read++
	if r.inspect != nil {
		r.inspect()
	}
	return r.status, r.err
}

func (r *publicationRouter) SetRemoteAccess(ctx context.Context, listener string, enabled bool) (lightkeenetic.WebAccess, error) {
	r.writes++
	if listener != webTestListener || !enabled {
		return lightkeenetic.WebAccess{State: "conflict"}, lightkeenetic.ErrWebOwnership
	}
	if r.apply != nil {
		r.apply(ctx)
	}
	if err := ctx.Err(); err != nil {
		return lightkeenetic.WebAccess{}, err
	}
	return lightkeenetic.WebAccess{State: "enabled", URL: "https://brolight.router.example/"}, nil
}

func newPublicationApp(t *testing.T, status lightkeenetic.WebAccess) (*App, *publicationRouter) {
	t.Helper()
	app, _, _ := newTestApp(t)
	if err := os.MkdirAll(app.run, 0700); err != nil {
		t.Fatal(err)
	}
	router := &publicationRouter{status: status}
	app.router = router
	return app, router
}

func TestAutomaticWebAccessWaitsForRegisteredDomain(t *testing.T) {
	app, router := newPublicationApp(t, lightkeenetic.WebAccess{State: "unavailable"})
	ctx := context.Background()
	if done, conflict := app.tryRemoteAccess(ctx, webTestListener); done || conflict || router.writes != 0 {
		t.Fatal("publication must wait for a registered router domain")
	}

	router.status = lightkeenetic.WebAccess{State: "recovery"}
	if done, conflict := app.tryRemoteAccess(ctx, webTestListener); done || conflict || router.writes != 0 {
		t.Fatal("an unconfirmed recovery state must be observed without mutation")
	}
	router.status.CanEnable = true
	app.RunRemoteAccess(ctx, webTestListener)
	if router.read != 3 || router.writes != 1 {
		t.Fatalf("automatic recovery did not complete: reads=%d writes=%d", router.read, router.writes)
	}
}

func TestAutomaticWebAccessWaitsForConflictToClear(t *testing.T) {
	app, router := newPublicationApp(t, lightkeenetic.WebAccess{State: "conflict"})
	router.err = lightkeenetic.ErrWebOwnership
	ctx := context.Background()
	for i := 0; i < 2; i++ {
		if done, conflict := app.tryRemoteAccess(ctx, webTestListener); done || !conflict || router.writes != 0 {
			t.Fatal("an ownership conflict must be inspected without mutation")
		}
	}
	router.status = lightkeenetic.WebAccess{State: "disabled", CanEnable: true}
	router.err = nil
	app.RunRemoteAccess(ctx, webTestListener)
	if router.read != 3 || router.writes != 1 {
		t.Fatalf("publication did not resume after the conflict cleared: reads=%d writes=%d", router.read, router.writes)
	}
}

func TestAutomaticWebAccessRecognizesExistingPublication(t *testing.T) {
	app, router := newPublicationApp(t, lightkeenetic.WebAccess{
		State: "enabled", URL: "https://brolight.router.example/",
	})
	app.RunRemoteAccess(context.Background(), webTestListener)
	if router.read != 1 || router.writes != 0 {
		t.Fatalf("an enabled rule needed no writes: reads=%d writes=%d", router.read, router.writes)
	}
}

func TestAutomaticWebAccessStopsIfFullBROrayAppears(t *testing.T) {
	app, router := newPublicationApp(t, lightkeenetic.WebAccess{State: "disabled", CanEnable: true})
	if err := os.Mkdir(filepath.Join(filepath.Dir(app.root), "broray"), 0700); err != nil {
		t.Fatal(err)
	}
	app.RunRemoteAccess(context.Background(), webTestListener)
	if router.read != 0 || router.writes != 0 {
		t.Fatalf("full BROray must block router access: reads=%d writes=%d", router.read, router.writes)
	}
}

func TestAutomaticWebAccessLeavesNonstandardListenerAlone(t *testing.T) {
	app, router := newPublicationApp(t, lightkeenetic.WebAccess{State: "disabled", CanEnable: true})
	for _, address := range []string{"127.0.0.1:8080", "[::1]:8080", "0.0.0.0:8080", "192.168.1.1:18080"} {
		app.RunRemoteAccess(context.Background(), address)
	}
	if router.read != 0 || router.writes != 0 {
		t.Fatalf("nonstandard listeners contacted the router: reads=%d writes=%d", router.read, router.writes)
	}
}

func TestAutomaticWebAccessWaitsForInstallationCommit(t *testing.T) {
	app, router := newPublicationApp(t, lightkeenetic.WebAccess{State: "disabled", CanEnable: true})
	ctx := context.Background()
	lock, err := lightinstall.TryOperationLock(app.run)
	if err != nil {
		t.Fatal(err)
	}
	done, conflict := app.tryRemoteAccess(ctx, webTestListener)
	if err := lock.Close(); err != nil {
		t.Fatal(err)
	}
	if done || conflict || router.read != 1 || router.writes != 0 {
		t.Fatal("publication must stay read-only while the installer holds the operation lock")
	}

	if err := os.MkdirAll(app.root, 0700); err != nil {
		t.Fatal(err)
	}
	pending := filepath.Join(app.root, ".light-go-install.json")
	if err := os.WriteFile(pending, []byte(`{"committed":false}`), 0600); err != nil {
		t.Fatal(err)
	}
	if done, conflict := app.tryRemoteAccess(ctx, webTestListener); done || conflict || router.read != 1 || router.writes != 0 {
		t.Fatal("publication proceeded before installation was committed")
	}
	if err := os.WriteFile(pending, []byte(`{"committed":true}`), 0600); err != nil {
		t.Fatal(err)
	}
	app.RunRemoteAccess(ctx, webTestListener)
	if router.read != 2 || router.writes != 1 {
		t.Fatalf("publication did not resume after installation committed: reads=%d writes=%d", router.read, router.writes)
	}
}

func TestAutomaticWebAccessRechecksInstallationBeforeWriting(t *testing.T) {
	app, router := newPublicationApp(t, lightkeenetic.WebAccess{State: "disabled", CanEnable: true})
	if err := os.MkdirAll(app.root, 0700); err != nil {
		t.Fatal(err)
	}
	router.inspect = func() {
		if err := os.WriteFile(filepath.Join(app.root, ".light-go-install.json"), []byte(`{"committed":false}`), 0600); err != nil {
			t.Fatal(err)
		}
	}
	done, conflict := app.tryRemoteAccess(context.Background(), webTestListener)
	if done || conflict || router.read != 1 || router.writes != 0 {
		t.Fatal("publication wrote after installation began during inspection")
	}
}

func TestAutomaticWebAccessKeepsLocalReadinessIndependent(t *testing.T) {
	app, router := newPublicationApp(t, lightkeenetic.WebAccess{State: "disabled", CanEnable: true})
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	started, finished := make(chan struct{}), make(chan struct{})
	router.apply = func(ctx context.Context) {
		close(started)
		<-ctx.Done()
	}
	go func() {
		defer close(finished)
		app.RunRemoteAccess(ctx, webTestListener)
	}()
	select {
	case <-started:
	case <-ctx.Done():
		t.Fatal("background publication did not start")
	}
	if !app.mu.TryLock() {
		t.Fatal("background publication holds the mutex used by local readiness")
	}
	app.mu.Unlock()
	if err := app.ready(ctx); err != nil {
		t.Fatalf("local readiness while publication is active: %v", err)
	}
	cancel()
	select {
	case <-finished:
	case <-time.After(3 * time.Second):
		t.Fatal("background publication did not stop with the daemon")
	}
}
