package lightinstall

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"runtime"
	"strconv"
	"strings"
	"time"
)

const (
	Version      = "3.5.10"
	Product      = "BROray-Light"
	Channel      = "stable"
	ReleaseBase  = "https://github.com/BROadmin/BROray-Light/releases"
	ManifestName = "light-go-release.json"
	maxArchive   = 64 << 20
	// The existing BROray-Light Stable key.
	stableKey = "RWQffKs/yfer+Htw0zFJaTV9AqUUbnW/LhNu5WkCxyVsTpE/dHCiJvkm"
)

type Artifact struct {
	URL       string `json:"url"`
	SizeBytes int64  `json:"sizeBytes"`
	SHA256    string `json:"sha256"`
}

type Manifest struct {
	SchemaVersion int                 `json:"schemaVersion"`
	Product       string              `json:"product"`
	Channel       string              `json:"channel"`
	Version       string              `json:"version"`
	IssuedAt      time.Time           `json:"issuedAt"`
	ExpiresAt     time.Time           `json:"expiresAt"`
	Archives      map[string]Artifact `json:"archives"`
}

type Info struct {
	Version   string   `json:"version"`
	Available bool     `json:"available"`
	Archive   Artifact `json:"archive"`
}

func archiveHost(arch string) string {
	switch arch {
	case "mipsle":
		return "mipsel"
	case "arm":
		return "armv7"
	default:
		return arch
	}
}

func ArchiveName(version, platform string) string {
	return "broray-light-" + version + "-linux-" + platform + ".tar.gz"
}

func httpClient() *http.Client {
	return &http.Client{
		Timeout: 3 * time.Minute,
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			if len(via) >= 6 || !trustedReleaseURL(req.URL) {
				return errors.New("untrusted release redirect")
			}
			return nil
		},
	}
}

func trustedReleaseURL(u *url.URL) bool {
	if u.Scheme != "https" || u.User != nil || u.Port() != "" {
		return false
	}
	switch u.Host {
	case "github.com":
		return strings.HasPrefix(u.Path, "/BROadmin/BROray-Light/releases/")
	case "release-assets.githubusercontent.com", "objects.githubusercontent.com":
		return true
	default:
		return false
	}
}

func request(ctx context.Context, client *http.Client, address string) (*http.Response, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, address, nil)
	if err != nil {
		return nil, err
	}
	if !trustedReleaseURL(req.URL) {
		return nil, errors.New("untrusted release URL")
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode != http.StatusOK {
		_ = resp.Body.Close()
		if resp.StatusCode == http.StatusNotFound {
			return nil, errors.New("BROray-Light Go release file is unavailable")
		}
		return nil, fmt.Errorf("release download returned HTTP %d", resp.StatusCode)
	}
	return resp, nil
}

func fetchSmall(ctx context.Context, client *http.Client, address string, max int64) ([]byte, error) {
	resp, err := request(ctx, client, address)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(io.LimitReader(resp.Body, max+1))
	if err == nil && int64(len(data)) > max {
		return nil, errors.New("release metadata exceeds size limit")
	}
	return data, err
}

func validHash(digest string) bool {
	b, err := hex.DecodeString(digest)
	return err == nil && len(b) == sha256.Size && strings.ToLower(digest) == digest
}

func versionParts(value string) ([3]int, error) {
	var nums [3]int
	parts := strings.Split(value, ".")
	if len(parts) != len(nums) {
		return nums, errors.New("expected stable version x.y.z")
	}
	for i, p := range parts {
		n, err := strconv.Atoi(p)
		if err != nil || n < 0 || strconv.Itoa(n) != p {
			return nums, errors.New("invalid stable version")
		}
		nums[i] = n
	}
	return nums, nil
}

func newer(version, installed string) bool {
	a, errA := versionParts(version)
	b, errB := versionParts(installed)
	if errA != nil || errB != nil {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return a[i] > b[i]
		}
	}
	return false
}

func signedManifest(data, detached []byte, key string, now time.Time, platform string) (Info, error) {
	pk, err := ParsePublicKey(key)
	if err != nil {
		return Info{}, err
	}
	sig, err := ParseSignature(detached)
	if err != nil {
		return Info{}, err
	}
	if err := sig.Verify(pk, data); err != nil {
		return Info{}, err
	}
	var manifest Manifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return Info{}, err
	}
	if manifest.Product != Product || manifest.Channel != Channel || manifest.SchemaVersion != 1 {
		return Info{}, errors.New("unsupported BROray-Light Go release manifest")
	}
	if _, err := versionParts(manifest.Version); err != nil {
		return Info{}, err
	}
	if now.Year() < 2025 || manifest.IssuedAt.IsZero() || manifest.IssuedAt.After(now.Add(10*time.Minute)) ||
		!manifest.ExpiresAt.After(manifest.IssuedAt) || !manifest.ExpiresAt.After(now) {
		return Info{}, errors.New("release manifest validity period is invalid")
	}
	artifact, ok := manifest.Archives[platform]
	if !ok {
		return Info{}, fmt.Errorf("release has no archive for %s", platform)
	}
	expected := ReleaseBase + "/download/v" + manifest.Version + "/" + ArchiveName(manifest.Version, platform)
	if artifact.URL != expected || artifact.SizeBytes <= 0 || artifact.SizeBytes > maxArchive || !validHash(artifact.SHA256) {
		return Info{}, errors.New("invalid BROray-Light archive descriptor")
	}
	return Info{Version: manifest.Version, Available: newer(manifest.Version, Version), Archive: artifact}, nil
}

func Check(ctx context.Context) (Info, error) {
	client := httpClient()
	address := ReleaseBase + "/latest/download/" + ManifestName
	manifest, err := fetchSmall(ctx, client, address, 64<<10)
	if err != nil {
		return Info{}, err
	}
	detached, err := fetchSmall(ctx, client, address+".minisig", maxSigSize)
	if err != nil {
		return Info{}, err
	}
	return signedManifest(manifest, detached, stableKey, time.Now(), archiveHost(runtime.GOARCH))
}

func fetchArchive(ctx context.Context, dst io.Writer, artifact Artifact) error {
	resp, err := request(ctx, httpClient(), artifact.URL)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	digest := sha256.New()
	size, err := io.Copy(io.MultiWriter(dst, digest), io.LimitReader(resp.Body, artifact.SizeBytes+1))
	if err != nil {
		return err
	}
	if size != artifact.SizeBytes || hex.EncodeToString(digest.Sum(nil)) != artifact.SHA256 {
		return errors.New("release archive size or SHA-256 mismatch")
	}
	return nil
}
