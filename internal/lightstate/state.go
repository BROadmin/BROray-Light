package lightstate

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"time"

	"github.com/BROadmin/broray-light/modules/servers"
)

type Entry struct {
	Profile  servers.Server `json:"profile"`
	Manual   bool           `json:"manual,omitempty"`
	Sources  []string       `json:"sources,omitempty"`
	Excluded bool           `json:"excluded,omitempty"`
	Renamed  bool           `json:"renamed,omitempty"`
}

type Subscription struct {
	ID             string    `json:"id"`
	Name           string    `json:"name"`
	URL            string    `json:"url"`
	RefreshMinutes int       `json:"refreshMinutes"`
	RefreshedAt    time.Time `json:"refreshedAt"`
}

type Failover struct {
	Enabled         bool `json:"enabled"`
	Threshold       int  `json:"threshold"`
	CooldownSeconds int  `json:"cooldownSeconds"`
}

type State struct {
	Schema                  int            `json:"schema"`
	Servers                 []Entry        `json:"servers"`
	Subscriptions           []Subscription `json:"subscriptions"`
	Active                  string         `json:"active"`
	ManageInterface         bool           `json:"manageInterface"`
	InterfaceCleanupPending bool           `json:"interfaceCleanupPending,omitempty"`
	Failover                Failover       `json:"failover"`
}

type Store struct{ path string }

func NewStore(root string) Store { return Store{filepath.Join(root, "state", "light.json")} }

func (s Store) Load() (State, error) {
	data, err := os.ReadFile(s.path)
	if errors.Is(err, os.ErrNotExist) {
		return State{Schema: 1, Failover: Failover{Threshold: 3, CooldownSeconds: 120}}, nil
	}
	if err != nil {
		return State{}, err
	}
	var state State
	if err := json.Unmarshal(data, &state); err != nil {
		return State{}, err
	}
	if state.Schema != 1 {
		return State{}, errors.New("unsupported Light state schema")
	}
	return state, nil
}

func (s Store) Save(state State) (bool, error) {
	data, err := json.MarshalIndent(state, "", "  ")
	if err != nil {
		return false, err
	}
	return AtomicWrite(s.path, data)
}

// AtomicWrite follows the donor's write, sync, rename and directory sync.
// It reports a visible rename even if syncing the directory fails.
func AtomicWrite(path string, data []byte) (committed bool, err error) {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0700); err != nil {
		return false, err
	}
	file, err := os.CreateTemp(dir, ".light-*")
	if err != nil {
		return false, err
	}
	defer os.Remove(file.Name())
	if _, err := file.Write(data); err != nil {
		file.Close()
		return false, err
	}
	if err := file.Sync(); err != nil {
		file.Close()
		return false, err
	}
	if err := file.Close(); err != nil {
		return false, err
	}
	if err := os.Rename(file.Name(), path); err != nil {
		return false, err
	}
	parent, err := os.Open(dir)
	if err != nil {
		return true, err
	}
	defer parent.Close()
	return true, parent.Sync()
}

func (s State) Clone() State {
	s.Servers = slices.Clone(s.Servers)
	for i := range s.Servers {
		s.Servers[i].Sources = slices.Clone(s.Servers[i].Sources)
	}
	s.Subscriptions = slices.Clone(s.Subscriptions)
	return s
}

func (s State) Find(id string) int {
	return slices.IndexFunc(s.Servers, func(entry Entry) bool { return entry.Profile.ID == id })
}

func (s State) FindSubscription(id string) int {
	return slices.IndexFunc(s.Subscriptions, func(sub Subscription) bool { return sub.ID == id })
}

// ProfileKey ignores labels and source metadata. Rotation identity additionally
// permits SNI and Reality short ID changes within one unambiguous feed entry.
func ProfileKey(profile servers.Server) string { return profileKey(profile, false) }

func profileKey(profile servers.Server, rotation bool) string {
	if rotation {
		profile.Reality.ServerName = ""
		profile.Reality.ShortID = ""
		profile.TLS.ServerName = ""
	}
	profile.Address = strings.ToLower(profile.Address)
	data, _ := json.Marshal(servers.Outbound(profile))
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func (s *State) ImportManual(profiles []servers.Server) int   { return s.merge("", profiles) }
func (s *State) Refresh(id string, profiles []servers.Server) { s.merge(id, profiles) }

func (s *State) merge(source string, profiles []servers.Server) int {
	exact := make(map[string]int, len(s.Servers))
	oldRotation := make(map[string][]int)
	newRotation := make(map[string]int)
	for i, entry := range s.Servers {
		exact[ProfileKey(entry.Profile)] = i
		if source != "" && slices.Equal(entry.Sources, []string{source}) && !entry.Manual {
			key := profileKey(entry.Profile, true)
			oldRotation[key] = append(oldRotation[key], i)
		}
	}
	seen := make(map[string]bool)
	unique := make([]servers.Server, 0, len(profiles))
	for _, profile := range profiles {
		key := ProfileKey(profile)
		if seen[key] {
			continue
		}
		seen[key] = true
		newRotation[profileKey(profile, true)]++
		unique = append(unique, profile)
	}
	matches := make(map[int]bool)
	added := 0
	for _, profile := range unique {
		key := ProfileKey(profile)
		index, exists := exact[key]
		if !exists && source != "" {
			rotation := profileKey(profile, true)
			prior := oldRotation[rotation]
			if newRotation[rotation] == 1 && len(prior) == 1 {
				index, exists = prior[0], true
			}
		}
		if !exists {
			profile.ID = servers.NewID()
			index = len(s.Servers)
			s.Servers = append(s.Servers, Entry{Profile: profile})
			added++
		}
		entry := &s.Servers[index]
		if exists && source != "" && !entry.Manual && slices.Equal(entry.Sources, []string{source}) {
			profile.ID = entry.Profile.ID
			if entry.Renamed {
				profile.Name = entry.Profile.Name
			}
			entry.Profile = profile
		}
		if source == "" {
			entry.Manual = true
		} else if !slices.Contains(entry.Sources, source) {
			entry.Sources = append(entry.Sources, source)
		}
		matches[index] = true
	}
	if source != "" {
		for i := range s.Servers {
			if !matches[i] {
				s.Servers[i].Sources = slices.DeleteFunc(s.Servers[i].Sources, func(id string) bool { return id == source })
			}
		}
		s.Servers = slices.DeleteFunc(s.Servers, func(entry Entry) bool { return !entry.Manual && len(entry.Sources) == 0 })
	}
	return added
}
