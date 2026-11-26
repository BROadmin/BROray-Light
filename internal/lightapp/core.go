package lightapp

import (
	"context"
	"errors"

	"github.com/BROadmin/broray-light/internal/lightruntime"
	"github.com/BROadmin/broray-light/modules/servers"
)

type coreRuntime interface {
	CoreVersion(context.Context) (string, error)
	InstallCore(context.Context, *servers.Server, func(context.Context) error) error
}

func (a *App) core(ctx context.Context, install bool) (any, error) {
	core, ok := a.runtime.(coreRuntime)
	if !ok {
		return nil, errors.New("Xray maintenance is unavailable")
	}
	if !install {
		current, err := core.CoreVersion(ctx)
		return map[string]string{"installed": current, "pinned": lightruntime.CoreRelease}, err
	}
	var selected *servers.Server
	if a.runningID == a.state.Active && a.runningID != "" && a.runtime.Running() {
		previous := a.runningProfile
		selected = &previous
	} else if i := a.state.Find(a.state.Active); i >= 0 {
		profile := a.state.Servers[i].Profile
		selected = &profile
	}
	err := core.InstallCore(ctx, selected, func(op context.Context) error {
		if selected == nil {
			return a.stop()
		}
		return a.start(op, *selected)
	})
	if err == nil && selected != nil {
		a.readyOnce = true
		a.health = ""
	}
	return nil, err
}
