package lightapp

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/BROadmin/broray-light/internal/lightstate"
)

func requestDeleteInactive(a *App) (any, error) {
	req := httptest.NewRequest(http.MethodPost, "/api/action", strings.NewReader(`{"kind":"delete-inactive"}`))
	req.Header.Set("Content-Type", "application/json")
	return a.action(httptest.NewRecorder(), req)
}

func TestDeleteInactivePreservesSelectedServerAndRuntime(t *testing.T) {
	a, rt, _ := newTestApp(t)
	source := "sub-synthetic"
	nodes := parse(t, "vless://11111111-1111-4111-8111-111111111111@one.example.test:443\n"+
		"vless://11111111-1111-4111-8111-111111111111@two.example.test:443\n"+
		"vless://11111111-1111-4111-8111-111111111111@three.example.test:443")
	next := a.state.Clone()
	next.Subscriptions = []lightstate.Subscription{{ID: source, URL: "https://subscription.example.test/"}}
	next.Refresh(source, nodes)
	if _, err := a.save(next); err != nil {
		t.Fatal(err)
	}
	if _, err := requestDeleteInactive(a); err == nil || len(a.state.Servers) != 3 {
		t.Fatal("bulk deletion without an active profile must keep all rows")
	}
	active := a.state.Servers[1].Profile.ID
	if err := a.activate(context.Background(), active); err != nil {
		t.Fatal(err)
	}
	result, err := requestDeleteInactive(a)
	if err != nil || result.(map[string]int)["removed"] != 2 {
		t.Fatalf("delete result %v, error %v", result, err)
	}
	persisted, err := a.store.Load()
	if err != nil {
		t.Fatal(err)
	}
	if persisted.Active != active || len(persisted.Servers) != 1 || persisted.Servers[0].Profile.ID != active ||
		len(persisted.Servers[0].Sources) != 1 || persisted.Servers[0].Sources[0] != source ||
		len(persisted.Subscriptions) != 1 || rt.id != active || rt.starts != 1 || rt.stops != 0 {
		t.Fatal("bulk deletion disturbed the active server, ownership, or running Xray")
	}
	result, err = requestDeleteInactive(a)
	if err != nil || result.(map[string]int)["removed"] != 0 {
		t.Fatalf("repeat delete result %v, error %v", result, err)
	}
}
