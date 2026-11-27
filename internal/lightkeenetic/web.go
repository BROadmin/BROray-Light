package lightkeenetic

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"net/netip"
	"slices"
	"strconv"
	"strings"
	"time"
)

const (
	webName        = "brolight"
	webRule        = "ip http proxy " + webName
	webReceiptFile = "keenetic-web-access.json"
	webSteps       = 5
)

var (
	ErrWebOwnership          = errors.New("владение правилом удалённого доступа Keenetic не подтверждено")
	ErrWebUnavailable        = errors.New("KeenDNS/CrazeDNS или локальный адрес WebUI недоступен")
	ErrWebRecovery           = errors.New("операция с удалённым доступом Keenetic требует восстановления")
	errWebCommandUnavailable = errors.New("команда удалённого доступа недоступна в KeeneticOS")
)

// WebAccess describes the local configuration of the KeenDNS/CrazeDNS rule.
// An enabled URL still depends on the router's certificate and cloud access.
type WebAccess struct {
	State      string `json:"state"`
	URL        string `json:"url,omitempty"`
	CanEnable  bool   `json:"canEnable,omitempty"`
	CanDisable bool   `json:"canDisable,omitempty"`
}

type webReceipt struct {
	Schema       int
	Owner        string
	Phase        string
	Endpoint     netip.AddrPort
	Outside      string
	Proof        string
	Step         int
	WritePending bool
	SavePending  bool
}

func (c *Client) readWebReceipt() (*webReceipt, error) {
	raw, err := c.readReceipt(webReceiptFile)
	if err != nil || raw == nil {
		return nil, err
	}
	var r webReceipt
	if json.Unmarshal(raw, &r) != nil || r.Schema != 1 || r.Owner != "BROray-Light" ||
		!r.Endpoint.Addr().Is4() || !r.Endpoint.Addr().IsPrivate() || r.Endpoint.Port() == 0 ||
		(r.Proof != "" && !webDigest(r.Proof)) {
		return nil, ErrWebOwnership
	}
	switch r.Phase {
	case creating:
		if !webDigest(r.Outside) || r.Step < 0 || r.Step > webSteps || (r.Step == 0) != (r.Proof == "") {
			return nil, ErrWebOwnership
		}
	case managed:
		if r.Outside != "" || r.Step != webSteps || r.Proof == "" || r.WritePending || r.SavePending {
			return nil, ErrWebOwnership
		}
	case cleaning:
		if !webDigest(r.Outside) || r.Step < 0 || r.Step > webSteps || (r.Step == 0) != (r.Proof == "") {
			return nil, ErrWebOwnership
		}
	default:
		return nil, ErrWebOwnership
	}
	if r.WritePending && r.SavePending || r.SavePending && r.Proof == "" ||
		r.Phase == creating && (r.SavePending && r.Step != webSteps || r.WritePending && r.Step == webSteps) {
		return nil, ErrWebOwnership
	}
	return &r, nil
}

func webDigest(s string) bool {
	if len(s) != 64 {
		return false
	}
	_, err := hex.DecodeString(s)
	return err == nil
}

func webFingerprint(lines configuration) string {
	if len(lines) == 0 {
		return ""
	}
	sum := sha256.Sum256([]byte(strings.Join(lines, "\n")))
	return hex.EncodeToString(sum[:])
}

type webImage struct {
	block   configuration
	outside string
	proof   string
}

func webImageOf(config configuration) (webImage, error) {
	start, end := -1, -1
	for i, line := range config {
		words := strings.Fields(line)
		if len(words) >= 4 && strings.EqualFold(strings.Join(words[:3], " "), "ip http proxy") &&
			strings.EqualFold(strings.Trim(words[3], "\"'"), webName) {
			if line != webRule || start != -1 {
				return webImage{}, ErrWebOwnership
			}
			start = i
			continue
		}
		if start >= 0 && end < 0 {
			if line == "!" {
				end = i
			} else if line == strings.TrimSpace(line) {
				return webImage{}, ErrWebOwnership
			}
		}
	}
	outside := config
	var block configuration
	if start >= 0 {
		if end < 0 {
			return webImage{}, ErrWebOwnership
		}
		block = config[start : end+1]
		outside = slices.Concat(config[:start], config[end+1:])
	}
	if references(outside, webName) != 0 {
		return webImage{}, ErrWebOwnership
	}
	return webImage{block: block, outside: webFingerprint(outside), proof: webFingerprint(block)}, nil
}

type webImages [2]webImage

func (c *Client) captureWeb(ctx context.Context) (webImages, error) {
	configs, err := c.capture(ctx)
	var images webImages
	if err != nil {
		return images, err
	}
	for i, config := range configs {
		images[i], err = webImageOf(config)
		if err != nil {
			return images, err
		}
	}
	return images, nil
}

func (im webImages) sameOutside() bool {
	return im[0].outside != "" && im[0].outside == im[1].outside
}

func (im webImages) owned(r *webReceipt) bool {
	if !im.sameOutside() {
		return false
	}
	for _, image := range im {
		if image.proof != "" && image.proof != r.Proof {
			return false
		}
	}
	return true
}

func (im webImages) known(r *webReceipt) bool {
	return im.owned(r) && im[0].outside == r.Outside
}

func webCommands(endpoint netip.AddrPort) [webSteps]string {
	return [webSteps]string{webRule, webRule + " ssl redirect",
		webRule + " upstream http " + endpoint.Addr().String() + " " + strconv.Itoa(int(endpoint.Port())),
		webRule + " security-level public", webRule + " domain ndns"}
}

// KeeneticOS can render redirect and private security immediately on
// construction. Require each explicit setting once configured, and reject
// an early association with NDNS.
func validWebBlock(block configuration, commands [webSteps]string, step int) bool {
	if len(block) < 2 || step < 1 || step > len(commands) {
		return false
	}
	var seen [webSteps]bool
	private := false
	for _, line := range block[1 : len(block)-1] {
		line = strings.TrimSpace(line)
		if line == "security-level private" {
			if private || step >= 4 {
				return false
			}
			private = true
			continue
		}
		const ssl = 1
		if line == "ssl redirect" {
			if seen[ssl] {
				return false
			}
			seen[ssl] = true
			continue
		}
		match := -1
		for i := 2; i < step; i++ {
			if line == strings.TrimPrefix(commands[i], webRule+" ") {
				match = i
				break
			}
		}
		if match < 0 || seen[match] {
			return false
		}
		seen[match] = true
	}
	return (step < 2 || seen[1]) && (step < 3 || seen[2]) &&
		(step < 4 || seen[3]) && (step < 5 || seen[4])
}

func webLabel(s string) bool {
	if len(s) == 0 || len(s) > 63 || s[0] == '-' || s[len(s)-1] == '-' {
		return false
	}
	for _, ch := range s {
		if !(ch >= 'a' && ch <= 'z' || ch >= '0' && ch <= '9' || ch == '-') {
			return false
		}
	}
	return true
}

func (c *Client) webTarget(ctx context.Context, listen string) (netip.AddrPort, string) {
	endpoint, err := netip.ParseAddrPort(listen)
	if err != nil || !endpoint.Addr().Is4() || !endpoint.Addr().IsPrivate() || endpoint.Port() == 0 {
		return netip.AddrPort{}, ""
	}
	lan, err := c.LANIPv4(ctx)
	if err != nil || lan != endpoint.Addr() {
		return netip.AddrPort{}, ""
	}
	reply, err := c.run(ctx, "show ndns")
	if err != nil {
		return endpoint, ""
	}
	v := fields(reply)
	name, domain := strings.ToLower(v["name"]), strings.ToLower(v["domain"])
	if !webLabel(name) || !strings.Contains(domain, ".") {
		return endpoint, ""
	}
	for _, label := range strings.Split(domain, ".") {
		if !webLabel(label) {
			return endpoint, ""
		}
	}
	host := webName + "." + name + "." + domain
	if len(host) > 253 {
		return endpoint, ""
	}
	return endpoint, "https://" + host + "/"
}

func webStatus(im webImages, r *webReceipt, endpoint netip.AddrPort, url string) WebAccess {
	absent := im[0].proof == "" && im[1].proof == ""
	if r == nil {
		switch {
		case !absent || !im.sameOutside():
			return WebAccess{State: "conflict"}
		case url == "":
			return WebAccess{State: "unavailable"}
		default:
			return WebAccess{State: "disabled", CanEnable: true}
		}
	}
	safe := absent || im.owned(r)
	if r.Phase != managed || absent {
		if r.WritePending {
			return WebAccess{State: "recovery", CanDisable: r.Phase == cleaning && im[0].proof == "" && safe}
		}
		if r.SavePending {
			switch r.Phase {
			case creating:
				confirmed := im.known(r) && im[0].proof == r.Proof && im[1].proof == r.Proof
				return WebAccess{State: "recovery", CanEnable: confirmed && r.Endpoint == endpoint && url != "", CanDisable: confirmed}
			case cleaning:
				return WebAccess{State: "recovery", CanDisable: absent}
			}
		}
		resumable := r.Phase == creating && im.known(r) &&
			(im[1].proof == "" || r.Step == webSteps && im[1].proof == r.Proof) &&
			(im[0].proof == r.Proof || absent) && r.Endpoint == endpoint && url != ""
		return WebAccess{State: "recovery", CanEnable: resumable, CanDisable: safe}
	}
	if im[0].proof != r.Proof || im[1].proof != r.Proof ||
		!validWebBlock(im[0].block, webCommands(r.Endpoint), webSteps) {
		return WebAccess{State: "conflict"}
	}
	if r.Endpoint != endpoint || url == "" {
		return WebAccess{State: "unavailable", CanDisable: safe}
	}
	return WebAccess{State: "enabled", URL: url, CanDisable: safe}
}

// RemoteAccess inspects the router without changing its configuration.
func (c *Client) RemoteAccess(ctx context.Context, listen string) (WebAccess, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	images, r, err := c.webSnapshot(ctx)
	if err != nil {
		return webFailureState(err), err
	}
	endpoint, url := c.webTarget(ctx, listen)
	return webStatus(images, r, endpoint, url), nil
}

func webFailureState(err error) WebAccess {
	if errors.Is(err, ErrWebOwnership) || errors.Is(err, ErrOwnership) {
		return WebAccess{State: "conflict"}
	}
	return WebAccess{State: "unavailable"}
}

func (c *Client) webSnapshot(ctx context.Context) (webImages, *webReceipt, error) {
	r, err := c.readWebReceipt()
	if err != nil {
		return webImages{}, nil, err
	}
	images, err := c.captureWeb(ctx)
	return images, r, err
}

// SetRemoteAccess publishes or removes Light's own website rule.
func (c *Client) SetRemoteAccess(ctx context.Context, listen string, enabled bool) (WebAccess, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	images, r, err := c.webSnapshot(ctx)
	if err != nil {
		return webFailureState(err), err
	}
	endpoint, url := c.webTarget(ctx, listen)
	status := webStatus(images, r, endpoint, url)
	if enabled {
		if status.State == "enabled" {
			return status, nil
		}
		if !status.CanEnable {
			return status, webStatusError(status)
		}
		err = c.enableWeb(ctx, images, r, endpoint)
		if err != nil {
			// A cancelled request can leave changes alive on the router.
			// Remove only what the durable receipt still independently proves.
			restoreCtx, cancel := context.WithTimeout(context.WithoutCancel(ctx), 25*time.Second)
			defer cancel()
			live, saved, restoreErr := c.webSnapshot(restoreCtx)
			if restoreErr == nil && saved != nil && saved.Phase == creating && !saved.WritePending && !saved.SavePending {
				restoreErr = c.disableWeb(restoreCtx, live, saved)
			}
			err = errors.Join(err, restoreErr)
		}
	} else if r != nil {
		if !status.CanDisable {
			return status, webStatusError(status)
		}
		err = c.disableWeb(ctx, images, r)
	} else if status.State == "conflict" {
		return status, ErrWebOwnership
	}
	inspectCtx, cancel := context.WithTimeout(context.WithoutCancel(ctx), 20*time.Second)
	defer cancel()
	images, r, stateErr := c.webSnapshot(inspectCtx)
	if stateErr != nil {
		return WebAccess{State: "recovery"}, errors.Join(err, stateErr)
	}
	endpoint, url = c.webTarget(inspectCtx, listen)
	status = webStatus(images, r, endpoint, url)
	if err == nil {
		if enabled && status.State != "enabled" {
			err = webStatusError(status)
		}
		if !enabled && (r != nil || images[0].proof != "" || images[1].proof != "") {
			err = ErrWebRecovery
		}
	}
	return status, err
}

func webStatusError(status WebAccess) error {
	switch status.State {
	case "conflict":
		return ErrWebOwnership
	case "recovery":
		return ErrWebRecovery
	case "enabled":
		return errUnsaved
	default:
		return ErrWebUnavailable
	}
}

func (c *Client) enableWeb(ctx context.Context, images webImages, r *webReceipt, endpoint netip.AddrPort) error {
	if r == nil {
		r = &webReceipt{Schema: 1, Owner: "BROray-Light", Phase: creating, Endpoint: endpoint, Outside: images[0].outside}
		if err := c.writeReceipt(webReceiptFile, r); err != nil {
			return err
		}
	} else if images[0].proof == "" && images[1].proof == "" && r.Step != 0 {
		// A reboot can discard a change that never reached startup.
		r.Step, r.Proof = 0, ""
		if err := c.writeReceipt(webReceiptFile, r); err != nil {
			return err
		}
	}
	commands := webCommands(endpoint)
	for r.Step < len(commands) {
		r.WritePending = true
		if err := c.writeReceipt(webReceiptFile, r); err != nil {
			return err
		}
		before, err := c.captureWeb(ctx)
		if err != nil || !before.known(r) || before[0].proof != r.Proof || before[1].proof != "" {
			return c.clearPendingWrite(r, errors.Join(err, ErrWebRecovery))
		}
		if err := c.webCommand(ctx, commands[r.Step]); err != nil {
			if errors.Is(err, errWebCommandUnavailable) {
				return c.clearPendingWrite(r, err)
			}
			return err
		}
		live, err := c.captureWeb(ctx)
		if err != nil {
			return err
		}
		if !live.sameOutside() || live[0].outside != r.Outside || live[1].proof != "" ||
			!validWebBlock(live[0].block, commands, r.Step+1) {
			if live.known(r) && live[0].proof == r.Proof && live[1].proof == "" {
				// The synchronous property command returned and the pre-state
				// remains visible. Its failure did not transfer ownership.
				return c.clearPendingWrite(r, ErrWebRecovery)
			}
			return ErrWebRecovery
		}
		r.Step, r.Proof, r.WritePending = r.Step+1, live[0].proof, false
		if err := c.writeReceipt(webReceiptFile, r); err != nil {
			return err
		}
		images = live
	}
	if images[1].proof == "" {
		if err := c.saveWeb(ctx, r); err != nil {
			return err
		}
	}
	after, err := c.captureWeb(ctx)
	if err != nil {
		return err
	}
	if !after.known(r) || after[0].proof != r.Proof || after[1].proof != r.Proof {
		return ErrWebRecovery
	}
	r.Phase, r.Outside, r.SavePending = managed, "", false
	return c.writeReceipt(webReceiptFile, r)
}

func (c *Client) disableWeb(ctx context.Context, im webImages, r *webReceipt) error {
	if im[0].proof == "" && im[1].proof == "" {
		return c.removeReceipt(webReceiptFile)
	}
	if !im.owned(r) {
		return ErrWebOwnership
	}
	r.Phase, r.Outside, r.WritePending, r.SavePending = cleaning, im[0].outside, im[0].proof != "", false
	if err := c.writeReceipt(webReceiptFile, r); err != nil {
		return err
	}
	if r.WritePending {
		check, err := c.captureWeb(ctx)
		if err != nil || !check.known(r) || check[0].proof != im[0].proof || check[1].proof != im[1].proof {
			return c.clearPendingWrite(r, errors.Join(err, ErrWebRecovery))
		}
		if err := c.webCommand(ctx, "no "+webRule); err != nil {
			if errors.Is(err, errWebCommandUnavailable) {
				return c.clearPendingWrite(r, err)
			}
			return err
		}
	}
	before, err := c.captureWeb(ctx)
	if err != nil {
		return err
	}
	if !before.known(r) || before[0].proof != "" {
		return ErrWebRecovery
	}
	r.WritePending = false
	if before[1].proof != "" {
		if err := c.saveWeb(ctx, r); err != nil {
			return err
		}
	}
	after, err := c.captureWeb(ctx)
	if err != nil {
		return err
	}
	if !after.known(r) || after[0].proof != "" || after[1].proof != "" {
		return ErrWebRecovery
	}
	return c.removeReceipt(webReceiptFile)
}

func (c *Client) clearPendingWrite(r *webReceipt, err error) error {
	r.WritePending = false
	return errors.Join(err, c.writeReceipt(webReceiptFile, r))
}

func (c *Client) saveWeb(ctx context.Context, r *webReceipt) error {
	r.SavePending = true
	if err := c.writeReceipt(webReceiptFile, r); err != nil {
		return err
	}
	before, err := c.captureWeb(ctx)
	want := r.Proof
	if r.Phase == cleaning {
		want = ""
	}
	if err != nil || !before.known(r) || before[0].proof != want {
		return c.clearPendingSave(r, errors.Join(err, ErrWebRecovery))
	}
	if before[1].proof == want {
		return nil
	}
	if err := c.webCommand(ctx, "system configuration save"); err != nil {
		if errors.Is(err, errWebCommandUnavailable) {
			return c.clearPendingSave(r, err)
		}
		return err
	}
	return c.wait(ctx)
}

func (c *Client) clearPendingSave(r *webReceipt, err error) error {
	r.SavePending = false
	return errors.Join(err, c.writeReceipt(webReceiptFile, r))
}

func (c *Client) webCommand(ctx context.Context, command string) error {
	reply, err := c.run(ctx, command)
	if err != nil {
		return err
	}
	reply = strings.ToLower(reply)
	if strings.Contains(reply, "no such command") || strings.Contains(reply, "unknown command") {
		return errWebCommandUnavailable
	}
	if strings.Contains(reply, "error") || strings.Contains(reply, "failed") {
		return errors.New("Keenetic отклонил изменение удалённого доступа WebUI")
	}
	return nil
}
