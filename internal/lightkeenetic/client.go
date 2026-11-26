// Package lightkeenetic manages Light's native Keenetic proxy interface.
package lightkeenetic

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"net/netip"
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/BROadmin/broray-light/internal/keenetic"
)

var (
	ErrOwnership = errors.New("владение прокси-интерфейсом Keenetic не подтверждено")
	ErrNotReady  = errors.New("прокси-интерфейс Keenetic ещё не подключён")
	errUnsaved   = errors.New("в конфигурации Keenetic есть другие несохранённые изменения")
	errPending   = errors.New("предыдущая операция с интерфейсом Keenetic требует завершения")
)

type Client struct {
	stateDir string
	run      func(context.Context, string) (string, error)
	settle   time.Duration
	mu       sync.Mutex
	authMu   sync.Mutex
	authHost netip.Addr
	verifier *keenetic.Verifier
}

func New(stateDir string) *Client {
	return &Client{stateDir: stateDir, run: ndmc, settle: 5 * time.Second}
}

// LANIPv4 returns Bridge0's private IPv4 address as reported by Keenetic.
func (c *Client) LANIPv4(ctx context.Context) (netip.Addr, error) {
	if reply, err := c.run(ctx, "show interface Bridge0"); err == nil {
		if address, ok := privateIPv4(fields(reply)["address"]); ok {
			return address, nil
		}
	}
	config, err := c.config(ctx, "show running-config")
	if err == nil {
		block, err := extract(config, "Bridge0")
		if err == nil {
			for _, line := range block {
				if words := strings.Fields(line); len(words) >= 4 && words[0] == "ip" && words[1] == "address" {
					if address, ok := privateIPv4(words[2]); ok {
						return address, nil
					}
				}
			}
		}
	}
	return netip.Addr{}, keenetic.ErrUnavailable
}

func privateIPv4(value string) (netip.Addr, bool) {
	address, err := netip.ParseAddr(value)
	return address, err == nil && address.Is4() && address.IsPrivate()
}

func (c *Client) Authenticate(ctx context.Context, user, password string) error {
	host, err := c.LANIPv4(ctx)
	if err != nil {
		return err
	}
	c.authMu.Lock()
	if c.verifier == nil || c.authHost != host {
		c.verifier, err = keenetic.NewVerifier(keenetic.ManagementEndpoint{Address: host, Port: 80})
		if err != nil {
			c.authMu.Unlock()
			return keenetic.ErrUnavailable
		}
		c.authHost = host
	}
	verifier := c.verifier
	c.authMu.Unlock()
	return verifier.Verify(ctx, user, password)
}

// Ensure configures an unused native proxy name or resumes its creation/
// reconfiguration using Light's durable receipt.
func (c *Client) Ensure(ctx context.Context, socksAddress string) error {
	endpoint, err := socksEndpoint(socksAddress)
	if err != nil {
		return err
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	owned, err := c.load()
	if err != nil {
		return err
	}
	sn, err := c.capture(ctx)
	if err != nil {
		return err
	}
	if owned == nil {
		name, err := freeName(sn)
		if err != nil {
			return err
		}
		if !sn.sameOutside(name) {
			return errUnsaved
		}
		owned, err = newReceipt(name, endpoint)
		if err != nil {
			return err
		}
		if err := c.store(owned); err != nil {
			return err
		}
	}
	if owned.Phase == managed {
		if !sn.exact(owned) {
			return ErrOwnership
		}
		if owned.Endpoint == endpoint {
			return nil
		}
		if !sn.sameOutside(owned.Name) {
			return errUnsaved
		}
		owned.Phase, owned.Next = changing, endpoint
		if err := c.store(owned); err != nil {
			return err
		}
	}
	switch {
	case owned.Phase == changing && owned.Next == endpoint:
		return c.changeEndpoint(ctx, sn, owned)
	case owned.Phase == creating && owned.Endpoint == endpoint:
		return c.create(ctx, sn, owned)
	default:
		return errPending
	}
}

func (c *Client) create(ctx context.Context, sn snapshots, r *receipt) error {
	if sn.exact(r) {
		return c.commit(r)
	}
	for _, config := range sn {
		block, err := extract(config, r.Name)
		if err != nil {
			return err
		}
		if block != nil && !creationBlock(block, r) || block == nil && references(config, r.Name) != 0 {
			return ErrOwnership
		}
	}
	if !sn.sameOutside(r.Name) {
		return errUnsaved
	}
	base := "interface " + r.Name
	commands := []string{
		base + " description " + r.Description,
		base + " proxy protocol socks5",
		upstreamCommand(r.Name, r.Endpoint),
		base + " proxy connect",
		base + " security-level public",
		base + " up",
	}
	for _, command := range commands {
		if err := c.mutate(ctx, command); err != nil {
			return err
		}
	}
	return c.confirmAndSave(ctx, r)
}

func (c *Client) changeEndpoint(ctx context.Context, sn snapshots, r *receipt) error {
	target := *r
	target.Endpoint = r.Next
	for _, config := range sn {
		if !exactIn(config, r) && !exactIn(config, &target) {
			return ErrOwnership
		}
	}
	if !sn.sameOutside(r.Name) {
		return errUnsaved
	}
	if sn.exact(&target) {
		return c.commit(&target)
	}
	if err := c.mutate(ctx, upstreamCommand(r.Name, target.Endpoint)); err != nil {
		return err
	}
	if err := c.mutate(ctx, "interface "+r.Name+" proxy connect"); err != nil {
		return err
	}
	return c.confirmAndSave(ctx, &target)
}

func upstreamCommand(name string, endpoint netip.AddrPort) string {
	return "interface " + name + " proxy upstream " + endpoint.Addr().String() + " " + strconv.Itoa(int(endpoint.Port()))
}

func (c *Client) confirmAndSave(ctx context.Context, target *receipt) error {
	if err := c.wait(ctx); err != nil {
		return err
	}
	before, err := c.capture(ctx)
	if err != nil {
		return err
	}
	if !exactIn(before[0], target) || !before.sameOutside(target.Name) {
		return ErrOwnership
	}
	// The startup image must be unchanged or already exactly ours. Otherwise
	// an outside edit of the same interface would be lost on save.
	startup, err := extract(before[1], target.Name)
	if err != nil {
		return err
	}
	if target.Phase == creating {
		if startup != nil && !creationBlock(startup, target) || startup == nil && references(before[1], target.Name) != 0 {
			return ErrOwnership
		}
	} else {
		previous, err := c.load()
		if err != nil {
			return err
		}
		if previous == nil || !exactIn(before[1], previous) && !exactIn(before[1], target) {
			return ErrOwnership
		}
	}
	if err := c.mutate(ctx, "system configuration save"); err != nil {
		return err
	}
	after, err := c.capture(ctx)
	if err != nil {
		return err
	}
	if !after.exact(target) {
		return ErrOwnership
	}
	return c.commit(target)
}

func (c *Client) commit(r *receipt) error {
	r.Phase, r.Next = managed, netip.AddrPort{}
	return c.store(r)
}

// Ready rechecks native interface settings and status without changing them.
func (c *Client) Ready(ctx context.Context, socksAddress string) error {
	endpoint, err := socksEndpoint(socksAddress)
	if err != nil {
		return err
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	r, err := c.load()
	if err != nil {
		return err
	}
	if r == nil || r.Phase != managed || r.Endpoint != endpoint {
		return ErrNotReady
	}
	check := func() error {
		sn, err := c.capture(ctx)
		if err == nil && !sn.exact(r) {
			return ErrOwnership
		}
		return err
	}
	if err := check(); err != nil {
		return err
	}
	reply, err := c.run(ctx, "show interface "+r.Name)
	if err != nil {
		return err
	}
	v := fields(reply)
	if v["type"] != "Proxy" || v["link"] != "up" || v["state"] != "up" ||
		v["connected"] != "yes" || v["description"] != r.Description {
		return ErrNotReady
	}
	return check()
}

// Cleanup only deletes the proven Light interface with no external references.
// It retains its durable receipt until running and startup both show removal.
func (c *Client) Cleanup(ctx context.Context) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	r, err := c.load()
	if err != nil || r == nil {
		return err
	}
	if r.Phase == changing {
		return errPending
	}
	sn, err := c.capture(ctx)
	if err != nil {
		return err
	}
	var present [2]bool
	for i, config := range sn {
		present[i], err = cleanupSafe(config, r)
		if err != nil {
			return err
		}
	}
	if !present[0] && !present[1] {
		return c.remove()
	}
	if !sn.sameOutside(r.Name) {
		return errUnsaved
	}
	if r.Phase != cleaning {
		r.Phase = cleaning
		if err := c.store(r); err != nil {
			return err
		}
	}
	if present[0] {
		if err := c.mutate(ctx, "no interface "+r.Name); err != nil {
			return err
		}
	}
	if err := c.wait(ctx); err != nil {
		return err
	}
	sn, err = c.capture(ctx)
	if err != nil {
		return err
	}
	if present, err := cleanupSafe(sn[0], r); err != nil || present || !sn.sameOutside(r.Name) {
		return ErrOwnership
	}
	if present, err := cleanupSafe(sn[1], r); err != nil {
		return err
	} else if present {
		if err := c.mutate(ctx, "system configuration save"); err != nil {
			return err
		}
	}
	sn, err = c.capture(ctx)
	if err != nil {
		return err
	}
	for _, config := range sn {
		if present, err := cleanupSafe(config, r); err != nil || present {
			return ErrOwnership
		}
	}
	return c.remove()
}

func (c *Client) wait(ctx context.Context) error {
	timer := time.NewTimer(c.settle)
	defer timer.Stop()
	select {
	case <-timer.C:
	case <-ctx.Done():
	}
	return ctx.Err()
}

func (c *Client) mutate(ctx context.Context, command string) error {
	reply, err := c.run(ctx, command)
	if err != nil {
		return err
	}
	reply = strings.ToLower(reply)
	if strings.Contains(reply, "error") || strings.Contains(reply, "failed") {
		return errors.New("Keenetic отклонил изменение интерфейса")
	}
	return nil
}

func ndmc(ctx context.Context, command string) (string, error) {
	ctx, cancel := context.WithTimeout(ctx, 15*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "/bin/ndmc", "-c", command)
	cmd.Env = []string{"LANG=C", "PATH=/bin:/sbin:/usr/bin:/usr/sbin"}
	stdout, stderr := boundedBuffer{limit: 4 << 20}, boundedBuffer{limit: 1024}
	cmd.Stdout, cmd.Stderr = &stdout, &stderr
	if err := cmd.Run(); err != nil || stderr.buffer.Len() != 0 || stdout.overflow || stderr.overflow {
		return "", fmt.Errorf("ndmc: %s: %w", command, errors.Join(err, errors.New("ответ Keenetic не подтверждён")))
	}
	return stdout.buffer.String(), nil
}

type boundedBuffer struct {
	buffer   bytes.Buffer
	limit    int
	overflow bool
}

func (b *boundedBuffer) Write(data []byte) (int, error) {
	size := len(data)
	if remaining := b.limit - b.buffer.Len(); size > remaining {
		b.overflow = true
		data = data[:remaining]
	}
	_, _ = b.buffer.Write(data)
	return size, nil
}

func fields(reply string) map[string]string {
	result := make(map[string]string)
	seen := make(map[string]bool)
	for line := range strings.SplitSeq(reply, "\n") {
		key, value, found := strings.Cut(strings.TrimSpace(line), ":")
		if !found {
			continue
		}
		if seen[key] {
			delete(result, key)
		} else {
			result[key] = strings.TrimSpace(value)
		}
		seen[key] = true
	}
	return result
}

func socksEndpoint(address string) (netip.AddrPort, error) {
	endpoint, err := netip.ParseAddrPort(address)
	if err != nil || !endpoint.Addr().Is4() || endpoint.Addr().IsUnspecified() ||
		endpoint.Addr().IsMulticast() || endpoint.Port() == 0 {
		return netip.AddrPort{}, errors.New("неверный IPv4-адрес локального SOCKS-интерфейса")
	}
	return endpoint, nil
}
