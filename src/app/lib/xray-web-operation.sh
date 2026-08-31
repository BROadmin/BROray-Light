#!/opt/bin/ash
BRORAY_ROOT="${BRORAY_ROOT:-/opt/broray-light}"; . "$BRORAY_ROOT/lib/operation-lock.sh"; . "$BRORAY_ROOT/lib/xray-control.sh"; . "$BRORAY_ROOT/lib/xray-update.sh"
broray_xray_web_update(){ rc=0; broray_operation_lock_acquire xray-update || rc=$?; [ "$rc" -eq 0 ] || return "$rc"; trap 'broray_operation_lock_release >/dev/null 2>&1 || true' EXIT; broray_xray_update_install update; }
