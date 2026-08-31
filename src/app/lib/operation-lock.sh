#!/opt/bin/ash
BRORAY_LIGHT_LOCK_ROOT="${BRORAY_LIGHT_LOCK_ROOT:-/opt/var/lock/broray-light}"
BRORAY_LIGHT_GLOBAL_LOCK="$BRORAY_LIGHT_LOCK_ROOT/global-operation.lock"
BRORAY_LIGHT_UPDATER_LOCK="${BRORAY_LIGHT_UPDATER_LOCK:-/opt/var/lock/broray-light-updater/request.lock}"
broray_operation_lock_owner_alive(){ p="$1"; case "$p" in ''|*[!0-9]*) return 1;; esac; kill -0 "$p" 2>/dev/null; }
broray_operation_lock_acquire(){
  operation="${1:-operation}"; mkdir -p "$BRORAY_LIGHT_LOCK_ROOT" || return 1
  [ ! -e "$BRORAY_LIGHT_UPDATER_LOCK" ] || return 2
  if mkdir "$BRORAY_LIGHT_GLOBAL_LOCK" 2>/dev/null; then
    printf '%s\n' "$$" > "$BRORAY_LIGHT_GLOBAL_LOCK/pid" || return 1
    printf '%s\n' "$operation" > "$BRORAY_LIGHT_GLOBAL_LOCK/operation"
    date '+%Y-%m-%dT%H:%M:%S%z' > "$BRORAY_LIGHT_GLOBAL_LOCK/startedAt"; return 0
  fi
  old="$(cat "$BRORAY_LIGHT_GLOBAL_LOCK/pid" 2>/dev/null || true)"
  if ! broray_operation_lock_owner_alive "$old"; then
    rm -rf "$BRORAY_LIGHT_GLOBAL_LOCK" || return 1
    mkdir "$BRORAY_LIGHT_GLOBAL_LOCK" 2>/dev/null || return 2
    printf '%s\n' "$$" > "$BRORAY_LIGHT_GLOBAL_LOCK/pid" || return 1
    printf '%s\n' "$operation" > "$BRORAY_LIGHT_GLOBAL_LOCK/operation"
    date '+%Y-%m-%dT%H:%M:%S%z' > "$BRORAY_LIGHT_GLOBAL_LOCK/startedAt"; return 0
  fi
  return 2
}
broray_operation_lock_release(){
  [ -d "$BRORAY_LIGHT_GLOBAL_LOCK" ] || return 0
  owner="$(cat "$BRORAY_LIGHT_GLOBAL_LOCK/pid" 2>/dev/null || true)"; [ "$owner" = "$$" ] || return 1
  rm -rf "$BRORAY_LIGHT_GLOBAL_LOCK"
}
