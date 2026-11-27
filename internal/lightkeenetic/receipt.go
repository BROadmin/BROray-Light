package lightkeenetic

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"net/netip"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"slices"
	"strconv"
	"strings"
)

const (
	creating          = "creating"
	managed           = "managed"
	changing          = "changing"
	cleaning          = "cleaning"
	receiptFile       = "keenetic-interface.json"
	descriptionPrefix = "BROray-Light-"
)

type receipt struct {
	Schema      int
	Owner       string
	Phase       string
	Name        string
	Description string
	Endpoint    netip.AddrPort
	Next        netip.AddrPort
}

func newReceipt(name string, endpoint netip.AddrPort) (*receipt, error) {
	var nonce [16]byte
	if _, err := rand.Read(nonce[:]); err != nil {
		return nil, err
	}
	return &receipt{Schema: 1, Owner: "BROray-Light", Phase: creating, Name: name,
		Description: descriptionPrefix + hex.EncodeToString(nonce[:]), Endpoint: endpoint}, nil
}

func (r *receipt) valid() bool {
	if r.Schema != 1 || r.Owner != "BROray-Light" || !validProxyName(r.Name) ||
		!strings.HasPrefix(r.Description, descriptionPrefix) || len(r.Description) != len(descriptionPrefix)+32 {
		return false
	}
	if _, err := hex.DecodeString(strings.TrimPrefix(r.Description, descriptionPrefix)); err != nil ||
		strings.ToLower(r.Description[len(descriptionPrefix):]) != r.Description[len(descriptionPrefix):] {
		return false
	}
	if _, err := socksEndpoint(r.Endpoint.String()); err != nil {
		return false
	}
	switch r.Phase {
	case creating, managed, cleaning:
		return r.Next == (netip.AddrPort{})
	case changing:
		_, err := socksEndpoint(r.Next.String())
		return err == nil && r.Next != r.Endpoint
	}
	return false
}

func (c *Client) load() (*receipt, error) {
	raw, err := c.readReceipt(receiptFile)
	if raw == nil || err != nil {
		return nil, err
	}
	var r receipt
	if json.Unmarshal(raw, &r) != nil || !r.valid() {
		return nil, ErrOwnership
	}
	return &r, nil
}

func (c *Client) readReceipt(name string) ([]byte, error) {
	path := filepath.Join(c.stateDir, name)
	info, err := os.Lstat(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if !info.Mode().IsRegular() || info.Size() > 4096 {
		return nil, ErrOwnership
	}
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	st, err := f.Stat()
	if err != nil || !os.SameFile(info, st) {
		return nil, ErrOwnership
	}
	raw, err := io.ReadAll(io.LimitReader(f, 4097))
	if err != nil {
		return nil, err
	}
	if len(raw) > 4096 {
		return nil, ErrOwnership
	}
	return raw, nil
}

func (c *Client) store(r *receipt) error {
	if !r.valid() {
		return ErrOwnership
	}
	return c.writeReceipt(receiptFile, r)
}

func (c *Client) writeReceipt(name string, r any) error {
	if err := os.MkdirAll(c.stateDir, 0o700); err != nil {
		return err
	}
	info, err := os.Lstat(c.stateDir)
	if err != nil || !info.IsDir() {
		return ErrOwnership
	}
	f, err := os.CreateTemp(c.stateDir, ".keenetic-receipt-")
	if err != nil {
		return err
	}
	defer os.Remove(f.Name())
	writeErr := json.NewEncoder(f).Encode(r)
	if writeErr == nil {
		writeErr = f.Sync()
	}
	if err := errors.Join(writeErr, f.Close()); err != nil {
		return err
	}
	if err := os.Rename(f.Name(), filepath.Join(c.stateDir, name)); err != nil {
		return err
	}
	return syncDirectory(c.stateDir)
}

func (c *Client) remove() error {
	return c.removeReceipt(receiptFile)
}

func (c *Client) removeReceipt(name string) error {
	if err := os.Remove(filepath.Join(c.stateDir, name)); err != nil && !errors.Is(err, os.ErrNotExist) {
		return err
	}
	return syncDirectory(c.stateDir)
}

func syncDirectory(path string) error {
	if runtime.GOOS == "windows" {
		return nil
	}
	dir, err := os.Open(path)
	if err != nil {
		return err
	}
	defer dir.Close()
	return dir.Sync()
}

type configuration []string
type snapshots [2]configuration

func (c *Client) config(ctx context.Context, command string) (configuration, error) {
	raw, err := c.run(ctx, command)
	if err != nil {
		return nil, err
	}
	var normalized configuration
	for line := range strings.SplitSeq(raw, "\n") {
		line = strings.TrimRight(line, " \t\r")
		if line != "" && !strings.HasPrefix(line, "! ") {
			normalized = append(normalized, line)
		}
	}
	if len(normalized) < 2 || !slices.Contains(normalized, "!") {
		return nil, errors.New("неполный снимок конфигурации Keenetic")
	}
	return normalized, nil
}

func (c *Client) capture(ctx context.Context) (snapshots, error) {
	var sn snapshots
	for i, command := range []string{"show running-config", "more startup-config"} {
		config, err := c.config(ctx, command)
		if err != nil {
			return sn, err
		}
		sn[i] = config
	}
	return sn, nil
}

func (sn snapshots) exact(r *receipt) bool {
	return exactIn(sn[0], r) && exactIn(sn[1], r)
}

func (sn snapshots) sameOutside(name string) bool {
	return slices.Equal(without(sn[0], name), without(sn[1], name))
}

func validProxyName(name string) bool {
	index, err := strconv.Atoi(strings.TrimPrefix(name, "Proxy"))
	return err == nil && index >= 0 && index <= 255 && name == "Proxy"+strconv.Itoa(index)
}

func freeName(sn snapshots) (string, error) {
	for i := 0; i <= 255; i++ {
		name := "Proxy" + strconv.Itoa(i)
		if references(sn[0], name) == 0 && references(sn[1], name) == 0 {
			return name, nil
		}
	}
	return "", errors.New("в Keenetic нет свободного имени прокси-интерфейса")
}

func references(config configuration, name string) int {
	count := 0
	for _, line := range config {
		for _, word := range strings.Fields(line) {
			if strings.EqualFold(strings.Trim(word, "\"'(),"), name) {
				count++
			}
		}
	}
	return count
}

func bounds(config configuration, name string) (start, end int, err error) {
	start, end = -1, -1
	parent := "interface " + name
	for i, line := range config {
		trimmed := strings.TrimSpace(line)
		if strings.EqualFold(trimmed, parent) {
			if line != parent || start >= 0 {
				return -1, -1, ErrOwnership
			}
			start = i
		} else if start >= 0 && end < 0 {
			if line == "!" {
				end = i
			} else if trimmed == line || strings.HasPrefix(trimmed, "interface ") {
				return -1, -1, ErrOwnership
			}
		}
	}
	if start >= 0 && end < 0 {
		return -1, -1, ErrOwnership
	}
	return start, end, nil
}

func extract(config configuration, name string) (configuration, error) {
	start, end, err := bounds(config, name)
	if err != nil || start < 0 {
		return nil, err
	}
	return config[start : end+1], nil
}

func without(config configuration, name string) configuration {
	start, end, err := bounds(config, name)
	if err != nil || start < 0 {
		return config
	}
	return append(append(configuration(nil), config[:start]...), config[end+1:]...)
}

var bindName = regexp.MustCompile("^[A-Za-z][A-Za-z0-9._/-]{0,63}$")

func matchesBlock(block configuration, r *receipt, partial bool) bool {
	if len(block) < 3 {
		return false
	}
	description := "description " + r.Description
	quoted := "description \"" + r.Description + "\""
	upstream := "proxy upstream " + r.Endpoint.Addr().String() + " " + strconv.Itoa(int(r.Endpoint.Port()))
	seen := make(map[string]bool, 7)
	for _, raw := range block[1 : len(block)-1] {
		line := strings.TrimSpace(raw)
		var key string
		switch line {
		case description, quoted:
			key = "description"
		case "security-level public":
			key = "security"
		case "proxy protocol socks5":
			key = "protocol"
		case upstream:
			key = "upstream"
		case "up":
			key = "admin"
		default:
			switch {
			case strings.HasPrefix(line, "ip global "):
				rawPriority := strings.TrimPrefix(line, "ip global ")
				priority, err := strconv.Atoi(rawPriority)
				if err != nil || priority < 1 || priority > 65534 || strconv.Itoa(priority) != rawPriority {
					return false
				}
				key = "priority"
			case strings.HasPrefix(line, "proxy connect via "):
				binding := strings.TrimPrefix(line, "proxy connect via ")
				if !bindName.MatchString(binding) || strings.Contains(binding, "..") || strings.Contains(binding, "//") ||
					strings.EqualFold(binding, r.Name) {
					return false
				}
				key = "binding"
			case partial && (line == "security-level protected" || line == "security-level private"):
				key = "security"
			case partial && line == "down":
				key = "admin"
			default:
				return false
			}
		}
		if seen[key] {
			return false
		}
		seen[key] = true
	}
	return seen["description"] && (partial || seen["security"] && seen["protocol"] && seen["upstream"] && seen["admin"])
}

func exactIn(config configuration, r *receipt) bool {
	block, err := extract(config, r.Name)
	return err == nil && matchesBlock(block, r, false)
}

func creationBlock(block configuration, r *receipt) bool {
	return matchesBlock(block, r, true)
}

func cleanupSafe(config configuration, r *receipt) (bool, error) {
	block, err := extract(config, r.Name)
	if err != nil {
		return false, err
	}
	refCount := references(config, r.Name)
	if block == nil && refCount == 0 {
		return false, nil
	}
	if refCount != 1 || !matchesBlock(block, r, false) {
		return false, ErrOwnership
	}
	return true, nil
}
