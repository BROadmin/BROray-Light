package lightinstall

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

const fixtureStatisticID = "0123456789abcdef0123456789abcdef"

func statisticsReceipt(kind string, committed bool) receipt {
	event := statisticEvent{EventID: fixtureStatisticID, Type: kind, Version: "3.5.10",
		Revision: statisticsRevision, Architecture: "arm64"}
	if kind == "update" {
		event.Version, event.Revision = "3.5.11", "light.r2"
		event.PreviousVersion, event.PreviousRevision = "3.5.10", statisticsRevision
	}
	return receipt{Committed: committed, PreviousVersion: event.PreviousVersion,
		Statistics: &installStatistic{Event: event}}
}

func TestInstallationStatisticsRecovery(t *testing.T) {
	for _, tc := range []struct {
		name string
		r    receipt
		want int
	}{
		{"confirmed install", statisticsReceipt("install", true), 1},
		{"confirmed update", statisticsReceipt("update", true), 1},
		{"rolled back install", statisticsReceipt("install", false), 0},
		{"pre-statistics receipt", receipt{Committed: true}, 0},
	} {
		t.Run(tc.name, func(t *testing.T) {
			l := testLayout(t)
			if err := l.record(tc.r); err != nil {
				t.Fatal(err)
			}
			for i := 0; i < 2; i++ {
				if err := l.recover(context.Background(), false); err != nil {
					t.Fatal(err)
				}
			}
			paths, err := statisticsFiles(l.root)
			if err != nil || len(paths) != tc.want || Pending(l.root) {
				t.Fatalf("after recovery: paths %v, pending %v, error %v", paths, Pending(l.root), err)
			}
			if tc.want == 1 && paths[0] != statisticsPath(l.root, fixtureStatisticID) {
				t.Fatalf("recovered outbox changed identity: %q", paths[0])
			}
		})
	}
}

func TestInstallationStatisticsDeliveryKeepsIdentityUntilAcknowledged(t *testing.T) {
	l := testLayout(t)
	r := statisticsReceipt("update", true)
	if err := l.record(r); err != nil {
		t.Fatal(err)
	}
	if err := l.finish(r); err != nil {
		t.Fatal(err)
	}
	var payloads []string
	var mu sync.Mutex
	srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		raw, err := io.ReadAll(req.Body)
		if err != nil || req.Method != "POST" || req.Header.Get("Content-Type") != "application/json" {
			t.Error("unexpected statistics request")
		}
		mu.Lock()
		defer mu.Unlock()
		payloads = append(payloads, string(raw))
		switch len(payloads) {
		case 1:
			w.WriteHeader(http.StatusServiceUnavailable)
		case 2:
			fmt.Fprint(w, `{"accepted":true,"eventId":"another-id"}`)
		case 3:
			fmt.Fprintf(w, `{"accepted":true,"eventId":%q}`, fixtureStatisticID)
		default:
			t.Error("unexpected extra attempt")
		}
	}))
	defer srv.Close()
	path := statisticsPath(l.root, fixtureStatisticID)
	now := time.Date(2026, time.November, 27, 0, 0, 0, 0, time.UTC)
	for i := 0; i < 3; i++ {
		done, err := deliverInstallStatistic(context.Background(), path, srv.Client(), srv.URL, now.Add(time.Duration(i)*time.Minute))
		if i == 2 && (!done || err != nil) || i != 2 && (done || err == nil) {
			t.Fatalf("attempt %d: done=%v error=%v", i+1, done, err)
		}
	}
	want, err := json.Marshal(r.Statistics.Event)
	if err != nil {
		t.Fatal(err)
	}
	mu.Lock()
	defer mu.Unlock()
	if len(payloads) != 3 || payloads[0] != string(want) || payloads[1] != payloads[0] || payloads[2] != payloads[0] {
		t.Fatalf("unexpected event payloads: %v", payloads)
	}
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatalf("acknowledged event remains: %v", err)
	}
}

func TestInstallationStatisticsExpiresBeforeDeduplicationWindow(t *testing.T) {
	l := testLayout(t)
	r := statisticsReceipt("install", true)
	now := time.Date(2026, time.November, 27, 0, 0, 0, 0, time.UTC)
	r.Statistics.FirstAttempt = now.Add(-statisticsWindow).Unix()
	if err := l.record(r); err != nil {
		t.Fatal(err)
	}
	if err := l.finish(r); err != nil {
		t.Fatal(err)
	}
	path := statisticsPath(l.root, fixtureStatisticID)
	done, err := deliverInstallStatistic(context.Background(), path, nil, "", now)
	if !done || err != nil {
		t.Fatalf("expired event retained: %v", err)
	}
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatalf("expired event remains: %v", err)
	}
}

func TestInstallationStatisticsOptOut(t *testing.T) {
	l := testLayout(t)
	args := []string{"--sha256", strings.Repeat("0", 64), "--no-install-statistics"}
	parsed, _, _, err := flags("install", args)
	if err != nil || !parsed.noStatistics {
		t.Fatalf("opt-out incorrectly parsed: %v", err)
	}
	path := statisticsDisabledPath(l.root)
	if err := os.WriteFile(path, []byte("disabled\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	if !statisticsDisabled(l.root) {
		t.Fatalf("opt-out not detected at %s", filepath.Base(path))
	}
}

func TestInstallationStatisticsClassifiesBuildChange(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	first := statisticBuild{Version: "3.5.10", Revision: "light.r1", Architecture: "arm64"}
	second := statisticBuild{Version: "3.5.11", Revision: "light.r1", Architecture: "arm64"}
	root := t.TempDir()
	initial := newInstallStatistic(ctx, root, first, statisticBuild{})
	upgrade := newInstallStatistic(ctx, root, second, first)
	if initial == nil || initial.Event.Type != "install" || upgrade == nil || upgrade.Event.Type != "update" ||
		initial.Event.EventID == upgrade.Event.EventID || upgrade.Event.PreviousVersion != first.Version {
		t.Fatalf("install and update events: %+v, %+v", initial, upgrade)
	}
	if got := newInstallStatistic(ctx, root, first, first); got != nil {
		t.Fatalf("same build produced an event: %+v", got)
	}
}
