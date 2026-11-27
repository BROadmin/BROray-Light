package lightapp

import (
	"context"
	"log"
	"net/netip"
	"time"

	"github.com/BROadmin/broray-light/internal/lightinstall"
)

// RunRemoteAccess publishes the standard LAN WebUI through KeenDNS when the
// router is ready. It runs independently of local HTTP and update readiness.
func (a *App) RunRemoteAccess(ctx context.Context, listen string) {
	addr, err := netip.ParseAddrPort(listen)
	if err != nil || !addr.Addr().Is4() || !addr.Addr().IsPrivate() || addr.Port() != 8080 {
		return
	}
	retry := 6 * time.Second
	warned := false
	for ctx.Err() == nil {
		done, conflict := a.tryRemoteAccess(ctx, listen)
		if done {
			return
		}
		if conflict && !warned {
			log.Print("KeenDNS/CrazeDNS: конфликт правила brolight или несохранённые настройки роутера")
			warned = true
		}
		select {
		case <-ctx.Done():
			return
		case <-time.After(retry):
		}
		retry = min(retry*2, 30*time.Second)
	}
}

// tryRemoteAccess inspects the router before taking the installer lock.
// Configuration writes exclude trial installs and leave local HTTP independent.
func (a *App) tryRemoteAccess(ctx context.Context, listen string) (done, conflict bool) {
	if err := NoFullProduct(a.root); err != nil {
		log.Printf("KeenDNS/CrazeDNS: %v", err)
		return true, false
	}
	if ctx.Err() != nil || lightinstall.Pending(a.root) {
		return false, false
	}

	inspect, cancelInspection := context.WithTimeout(ctx, 15*time.Second)
	status, err := a.router.RemoteAccess(inspect, listen)
	cancelInspection()
	if err == nil && status.CanEnable && (status.State == "disabled" || status.State == "recovery") {
		lock, lockErr := lightinstall.TryOperationLock(a.run)
		if lockErr != nil {
			return false, false
		}
		defer lock.Close()
		if err := NoFullProduct(a.root); err != nil {
			log.Printf("KeenDNS/CrazeDNS: %v", err)
			return true, false
		}
		if ctx.Err() != nil || lightinstall.Pending(a.root) {
			return false, false
		}
		attempt, cancel := context.WithTimeout(ctx, 55*time.Second)
		defer cancel()
		status, err = a.router.SetRemoteAccess(attempt, listen, true)
	}
	if status.State == "conflict" {
		return false, true
	}
	if err == nil && status.State == "enabled" && status.URL != "" {
		log.Printf("KeenDNS/CrazeDNS WebUI: %s", status.URL)
		return true, false
	}
	return false, false
}
