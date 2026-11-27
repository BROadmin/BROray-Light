package lightstate

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/BROadmin/broray-light/modules/servers"
)

func fixtureVLESS(t *testing.T, query string) servers.Server {
	t.Helper()
	profile, err := servers.ParseLink("vless://11111111-1111-4111-8111-111111111111@example.test:443?type=tcp&security=tls" + query)
	if err != nil {
		t.Fatal(err)
	}
	return profile
}

func TestVLESSRefreshRecoversDroppedOptionsWithoutChangingIdentity(t *testing.T) {
	full := fixtureVLESS(t, "&vcn=cert.example.test#Provider")
	plain := fixtureVLESS(t, "#Plain")
	legacy := full
	legacy.ID, legacy.Name, legacy.VLESSStream = "srv-old", "Renamed", nil
	if ProfileKey(legacy) != ProfileKey(plain) || ProfileKey(legacy) == ProfileKey(full) {
		t.Fatal("fixture does not model historical option loss")
	}
	for _, reverse := range []bool{false, true} {
		source := "sub-old"
		start := State{Schema: 1, Active: legacy.ID, Servers: []Entry{
			{Profile: legacy, Sources: []string{source}, Excluded: true, Renamed: true},
		}}
		store := NewStore(t.TempDir())
		raw, err := json.Marshal(start)
		if err != nil {
			t.Fatal(err)
		}
		if err := os.MkdirAll(filepath.Dir(store.path), 0o700); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(store.path, raw, 0o600); err != nil {
			t.Fatal(err)
		}
		state, err := store.Load()
		if err != nil {
			t.Fatal(err)
		}
		if ProfileKey(state.Servers[0].Profile) != ProfileKey(legacy) {
			t.Fatal("loading prior state changed the saved connection")
		}
		batch := []servers.Server{plain, full}
		if reverse {
			batch = []servers.Server{full, plain}
		}
		state.Refresh(source, batch)
		if len(state.Servers) != 2 || state.Active != legacy.ID {
			t.Fatalf("lost identity or duplicate config: active=%s len=%d", state.Active, len(state.Servers))
		}
		pinned := state.Servers[0]
		if pinned.Profile.ID != legacy.ID || pinned.Profile.Name != legacy.Name || !pinned.Excluded ||
			ProfileKey(pinned.Profile) != ProfileKey(full) || ProfileKey(state.Servers[1].Profile) != ProfileKey(plain) {
			t.Fatal("refreshed profile did not preserve the owned entry and separate options")
		}
		state.Refresh(source, batch)
		if len(state.Servers) != 2 || state.Active != legacy.ID {
			t.Fatal("refetch duplicated or displaced an existing profile")
		}
	}
}

func TestVLESSRefreshDoesNotUpgradeAnotherOwnersEntry(t *testing.T) {
	full := fixtureVLESS(t, "&vcn=cert.example.test")
	legacy := full
	legacy.ID, legacy.VLESSStream = "srv-old", nil
	state := State{Schema: 1, Active: legacy.ID, Servers: []Entry{
		{Profile: legacy, Sources: []string{"sub-old"}, Manual: true},
	}}
	state.Refresh("sub-old", []servers.Server{full})
	if len(state.Servers) != 2 || len(state.Servers[0].Sources) != 0 ||
		ProfileKey(state.Servers[0].Profile) != ProfileKey(legacy) || state.Active != legacy.ID {
		t.Fatal("refresh rewrote or removed the independently owned connection")
	}
}
