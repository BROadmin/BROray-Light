package lightinstall

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/tls"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"time"

	"github.com/BROadmin/broray-light/internal/lightkeenetic"
)

const (
	statisticsEndpoint = "https://stat.brovibe.cloud/v1/install-events"
	statisticsRevision = "light.r1"
	statisticsWindow   = 6 * 24 * time.Hour // The receiver keeps deduplication receipts for seven days.
	statisticsPrefix   = ".light-go-install-statistics-"
	statisticsMaxQueue = 64
)

var (
	statisticsID      = regexp.MustCompile(`^[a-f0-9]{32}$`)
	statisticsRelease = regexp.MustCompile(`^light\.[a-zA-Z0-9]{1,12}(\.[a-zA-Z0-9]{1,12})?$`)
	statisticsModel   = regexp.MustCompile(`^(KN|NC)-[0-9]{4}$`)
)

type statisticEvent struct {
	EventID          string `json:"eventId"`
	Type             string `json:"type"`
	Version          string `json:"version"`
	Revision         string `json:"revision"`
	Architecture     string `json:"architecture"`
	Model            string `json:"model,omitempty"`
	DeviceKey        string `json:"deviceKey,omitempty"`
	PreviousVersion  string `json:"previousVersion,omitempty"`
	PreviousRevision string `json:"previousRevision,omitempty"`
}

type installStatistic struct {
	Event        statisticEvent `json:"event"`
	FirstAttempt int64          `json:"firstAttempt,omitempty"`
}

func statisticsPath(root, id string) string {
	return filepath.Join(root, statisticsPrefix+id+".json")
}

func statisticsDisabledPath(root string) string {
	return filepath.Join(root, ".light-go-install-statistics-disabled")
}

func statisticsDisabled(root string) bool {
	_, err := os.Lstat(statisticsDisabledPath(root))
	return !errors.Is(err, os.ErrNotExist)
}

func statisticsFiles(root string) ([]string, error) {
	files, err := os.ReadDir(root)
	if err != nil {
		return nil, err
	}
	var paths []string
	for _, file := range files {
		name := file.Name()
		if id := strings.TrimSuffix(strings.TrimPrefix(name, statisticsPrefix), ".json"); statisticsID.MatchString(id) &&
			name == statisticsPrefix+id+".json" && file.Type().IsRegular() {
			paths = append(paths, filepath.Join(root, name))
		}
	}
	return paths, nil
}

func canRecordInstallStatistic(root string) bool {
	if statisticsDisabled(root) || statisticsArchitecture(runtime.GOARCH) == "" {
		return false
	}
	paths, err := statisticsFiles(root)
	if err != nil || len(paths) >= statisticsMaxQueue {
		log.Print("installation statistics outbox has no available slot")
		return false
	}
	return true
}

func statisticsArchitecture(arch string) string {
	switch arch {
	case "arm64":
		return arch
	case "arm":
		return "arm/7"
	case "mips", "mipsle":
		return arch + "/softfloat"
	default:
		return ""
	}
}

type statisticBuild struct {
	Version      string `json:"version"`
	Revision     string `json:"revision"`
	Architecture string `json:"architecture"`
}

// WriteStatisticsBuild reports metadata for the installer inspecting this binary.
func WriteStatisticsBuild(w io.Writer) error {
	return json.NewEncoder(w).Encode(statisticBuild{Version, statisticsRevision, statisticsArchitecture(runtime.GOARCH)})
}

func readStatisticBuild(ctx context.Context, binary, version string) statisticBuild {
	ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, binary, "version", "--build-json")
	out, err := cmd.StdoutPipe()
	if err != nil || cmd.Start() != nil {
		return statisticBuild{}
	}
	stopRead := context.AfterFunc(ctx, func() { _ = out.Close() })
	defer stopRead()
	raw, readErr := io.ReadAll(io.LimitReader(out, 513))
	if len(raw) > 512 || readErr != nil {
		out.Close()
	}
	runErr := cmd.Wait()
	var result statisticBuild
	if readErr != nil || len(raw) > 512 || runErr != nil || json.Unmarshal(raw, &result) != nil ||
		result.Version != version || !statisticsRelease.MatchString(result.Revision) ||
		result.Architecture != statisticsArchitecture(runtime.GOARCH) {
		return statisticBuild{}
	}
	return result
}

func newInstallStatistic(ctx context.Context, root string, after, before statisticBuild) *installStatistic {
	if after.Version == "" || after == before {
		return nil
	}
	var id [16]byte
	if _, err := rand.Read(id[:]); err != nil {
		log.Print("could not create the installation statistics identifier")
		return nil
	}
	event := statisticEvent{
		EventID: hex.EncodeToString(id[:]), Type: "install", Version: after.Version,
		Revision: after.Revision, Architecture: after.Architecture,
	}
	if before.Version != "" {
		event.Type = "update"
		event.PreviousVersion, event.PreviousRevision = before.Version, before.Revision
	}
	if !event.valid() {
		return nil
	}
	local, cancel := context.WithTimeout(ctx, 450*time.Millisecond)
	defer cancel()
	router := lightkeenetic.New(filepath.Join(root, "state"))
	event.Model, event.DeviceKey = router.InstallationStatisticsIdentity(local)
	return &installStatistic{Event: event}
}

func (e statisticEvent) valid() bool {
	if _, err := versionParts(e.Version); err != nil {
		return false
	}
	if !statisticsID.MatchString(e.EventID) || !statisticsRelease.MatchString(e.Revision) ||
		(e.Model != "" && !statisticsModel.MatchString(e.Model)) || (e.DeviceKey != "" && !validHash(e.DeviceKey)) {
		return false
	}
	switch e.Architecture {
	case "arm64", "arm/7", "mips/softfloat", "mipsle/softfloat":
	default:
		return false
	}
	switch e.Type {
	case "install":
		return e.PreviousVersion == "" && e.PreviousRevision == ""
	case "update":
		_, err := versionParts(e.PreviousVersion)
		return err == nil && statisticsRelease.MatchString(e.PreviousRevision) &&
			(e.PreviousVersion != e.Version || e.PreviousRevision != e.Revision)
	default:
		return false
	}
}

// RunInstallStatistics delivers the one confirmed installation event outside
// the installer lock. The daemon lock ensures only one sender per runtime.
func RunInstallStatistics(ctx context.Context, root string) {
	if statisticsArchitecture(runtime.GOARCH) == "" {
		return
	}
	transport := &http.Transport{TLSClientConfig: &tls.Config{MinVersion: tls.VersionTLS12}}
	defer transport.CloseIdleConnections()
	client := &http.Client{
		Transport: transport,
		Timeout:   8 * time.Second,
		CheckRedirect: func(*http.Request, []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
	retry := 5 * time.Second
	warned := false
	for ctx.Err() == nil {
		if statisticsDisabled(root) {
			return
		}
		sent, err := drainInstallStatistics(ctx, root, client)
		if err != nil && !warned && ctx.Err() == nil {
			log.Printf("installation statistics pending: %v", err)
			warned = true
		}
		if sent {
			retry = 5 * time.Second
		}
		select {
		case <-ctx.Done():
			return
		case <-time.After(retry):
		}
		retry = min(retry*2, 30*time.Minute)
		if err == nil {
			retry = min(retry, time.Minute)
		}
	}
}

func drainInstallStatistics(ctx context.Context, root string, client *http.Client) (bool, error) {
	paths, err := statisticsFiles(root)
	if err != nil {
		return false, err
	}
	sent := false
	for _, path := range paths[:min(len(paths), 4)] {
		if ctx.Err() != nil || statisticsDisabled(root) {
			break
		}
		done, err := deliverInstallStatistic(ctx, path, client, statisticsEndpoint, time.Now())
		sent = sent || done
		if err != nil {
			return sent, err
		}
	}
	return sent, nil
}

func deliverInstallStatistic(ctx context.Context, path string, client *http.Client, endpoint string, now time.Time) (bool, error) {
	raw, err := readLocal(path, 2048)
	if errors.Is(err, os.ErrNotExist) {
		return false, nil // The installer can still be confirming the running daemon.
	}
	if err != nil {
		return false, err
	}
	var r receipt
	if json.Unmarshal(raw, &r) != nil || !r.Committed || r.Statistics == nil ||
		!r.Statistics.Event.valid() || r.PreviousVersion != r.Statistics.Event.PreviousVersion ||
		path != statisticsPath(filepath.Dir(path), r.Statistics.Event.EventID) || r.Statistics.FirstAttempt < 0 {
		return false, errors.New("invalid installation statistics receipt")
	}
	if now.Year() < 2025 || now.Unix() < r.Statistics.FirstAttempt {
		return false, nil
	}
	if r.Statistics.FirstAttempt == 0 {
		r.Statistics.FirstAttempt = now.Unix()
		data, err := json.Marshal(r)
		if err != nil {
			return false, err
		}
		if err := atomicFile(path, 0o600, bytes.NewReader(data)); err != nil {
			return false, err
		}
	}
	if now.Sub(time.Unix(r.Statistics.FirstAttempt, 0)) >= statisticsWindow {
		err := removeFile(path)
		return err == nil, err
	}
	if err := sendInstallStatistic(ctx, client, endpoint, r.Statistics.Event); err != nil {
		return false, err
	}
	err = removeFile(path)
	return err == nil, err
}

func sendInstallStatistic(ctx context.Context, client *http.Client, endpoint string, event statisticEvent) error {
	raw, err := json.Marshal(event)
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(raw))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "BROray-Light-InstallStats/1")
	res, err := client.Do(req)
	if err != nil {
		return err
	}
	defer res.Body.Close()
	if res.StatusCode != http.StatusOK {
		return fmt.Errorf("receiver returned HTTP %d", res.StatusCode)
	}
	body, err := io.ReadAll(io.LimitReader(res.Body, 257))
	var ack struct {
		EventID  string `json:"eventId"`
		Accepted bool   `json:"accepted"`
	}
	if err != nil || len(body) > 256 || json.Unmarshal(body, &ack) != nil || !ack.Accepted || ack.EventID != event.EventID {
		return errors.New("receiver did not acknowledge the installation event")
	}
	return nil
}
