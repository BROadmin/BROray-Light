#!/opt/bin/ash
# Shared by the application and external updater. No persistent fallback.
# Root-owned private parents are the trust boundary; an administrator replacing
# their contents concurrently is outside this cooperative-process lock contract.

brl_ram_dir_valid()
{
    [ -d "$1" ] && [ ! -L "$1" ] &&
        [ "$(stat -c '%u:%a' "$1" 2>/dev/null)" = '0:700' ]
}

brl_ram_file_valid()
{
    [ -f "$1" ] && [ ! -L "$1" ] &&
        [ "$(stat -c '%u:%a' "$1" 2>/dev/null)" = '0:600' ]
}

brl_ram_namespace()
{
    local path marker
    path="$1"; marker="$2"
    if [ ! -e "$path" ] && [ ! -L "$path" ]; then
        # A process dying before marker publication leaves a refused namespace.
        # A concurrent initializer must return busy, never adopt partial state.
        (umask 077; mkdir "$path") 2>/dev/null || return 2
        (umask 077; set -C; printf '%s\n' "$marker" > "$path/owner") || return 3
    fi
    brl_ram_dir_valid "$path" && brl_ram_file_valid "$path/owner" &&
        [ "$(cat "$path/owner")" = "$marker" ] || return 3
}

brl_ram_child()
{
    if [ ! -e "$1" ] && [ ! -L "$1" ]; then
        (umask 077; mkdir "$1") 2>/dev/null || return 2
    fi
    brl_ram_dir_valid "$1"
}

brl_ram_prepare_app()
{
    local prefix base kind child
    prefix="${BRORAY_LIGHT_ROOT_PREFIX:-}"
    # Root-prefix exists solely for isolated-root tests and package lifecycle.
    case "$prefix" in ''|/*) ;; *) return 3 ;; esac
    case "$prefix" in */../*|*/..|*/./*|*/.|*//*|*/) return 3 ;; esac
    base="$prefix/tmp"
    [ "$(id -u)" = 0 ] || return 3
    [ -d "$base" ] && [ ! -L "$base" ] &&
        [ "$(stat -c '%u:%a' "$base" 2>/dev/null)" = '0:1777' ] || return 3
    kind="$(stat -f -c '%T' "$base" 2>/dev/null)" || return 3
    case "$kind" in tmpfs|ramfs) ;; *) return 3 ;; esac
    BRL_RAM="$base/broray-light"
    BRL_UPDATER_RAM="$base/broray-light-updater"
    brl_ram_namespace "$BRL_RAM" 'BROray-Light:runtime/1' || return $?
    for child in run tmp logs cache; do
        brl_ram_child "$BRL_RAM/$child" || return $?
    done
    for child in locks web-new; do
        brl_ram_child "$BRL_RAM/run/$child" || return $?
    done
    brl_ram_child "$BRL_RAM/run/web-new/sessions" || return $?
    BRL_GLOBAL_LOCK="$BRL_RAM/run/locks/global-operation.lock"
    BRL_REQUEST_LOCK="$BRL_UPDATER_RAM/request.lock"
    BRL_ADMISSION="$BRL_RAM/run/locks/admission"
    export BRL_RAM BRL_UPDATER_RAM BRL_GLOBAL_LOCK BRL_REQUEST_LOCK
}

brl_ram_prepare()
{
    brl_ram_prepare_app || return $?
    brl_ram_namespace "$BRL_UPDATER_RAM" 'BROray-Light:updater-runtime/1' || return $?
    brl_ram_child "$BRL_UPDATER_RAM/work"
}

brl_process_start()
{
    local raw rest
    case "$1" in ''|*[!0-9]*) return 1 ;; esac
    [ "$1" -gt 1 ] || return 1
    raw="$(cat "/proc/$1/stat" 2>/dev/null)" || return 1
    rest="${raw##*) }"
    [ "$rest" != "$raw" ] || return 1
    # State is field 3; starttime is field 22. No /proc environment hooks.
    printf '%s\n' "$rest" | awk 'NF>=20 && $1!="Z" && $1!="X" && $20~/^[0-9]+$/ {print $20; ok=1} END {if(!ok) exit 1}'
}

brl_legacy_locks_clear()
{
    local path
    for path in "${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/var/lock/broray-light/global-operation.lock" \
                "${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/var/lock/broray-light-updater/request.lock"; do
        # Read-only fence. Even a dangling or stale legacy lock is ambiguous
        # until the lifecycle migration has accounted for its transaction.
        [ ! -e "$path" ] && [ ! -L "$path" ] || return 2
    done
}

brl_admission_enter()
{
    local start
    start="$(brl_process_start "$$")" || return 3
    BRL_CLAIM="$(umask 077; mktemp "$BRL_RAM/run/locks/.claim.XXXXXX")" || return 3
    brl_ram_file_valid "$BRL_CLAIM" || return 3
    BRL_CLAIM_ID="$(stat -c '%d:%i' "$BRL_CLAIM")" || return 3
    printf 'BROray-Light:lock/1 %s %s\n' "$$" "$start" > "$BRL_CLAIM" || return 3
    # -T is required: a foreign directory must not receive our claim as a child.
    # Hard-link publication is no-replace and atomic, unlike mv -n emulation.
    if ! ln -T "$BRL_CLAIM" "$BRL_ADMISSION" 2>/dev/null; then
        rm -f "$BRL_CLAIM"
        BRL_CLAIM=''
        return 2
    fi
    brl_ram_file_valid "$BRL_ADMISSION" &&
        [ "$(stat -c '%d:%i' "$BRL_ADMISSION")" = "$BRL_CLAIM_ID" ]
}

brl_admission_leave()
{
    [ -n "${BRL_CLAIM:-}" ] && brl_ram_file_valid "$BRL_ADMISSION" &&
        brl_ram_file_valid "$BRL_CLAIM" &&
        [ "$(stat -c '%d:%i' "$BRL_ADMISSION")" = "$BRL_CLAIM_ID" ] &&
        [ "$(stat -c '%d:%i' "$BRL_CLAIM")" = "$BRL_CLAIM_ID" ] || return 3
    rm "$BRL_ADMISSION" "$BRL_CLAIM" || return 3
    BRL_CLAIM=''
}

brl_lock_shape()
{
    local children
    brl_ram_dir_valid "$1" && brl_ram_file_valid "$1/owner" || return 3
    children="$(find "$1" -mindepth 1 -maxdepth 1 -print | wc -l | tr -d ' ')" || return 3
    [ "$children" = 1 ] || return 3
    awk 'NR==1 && NF==3 && $1=="BROray-Light:lock/1" && $2~/^[0-9]+$/ && $2>1 && $3~/^[0-9]+$/ {ok=1} END {exit !(ok && NR==1)}' "$1/owner"
}

brl_lock_owner_alive()
{
    local pid start actual
    pid="$(awk '{print $2}' "$1/owner")"
    start="$(awk '{print $3}' "$1/owner")"
    actual="$(brl_process_start "$pid")" || return 1
    [ "$actual" = "$start" ] && kill -0 "$pid" 2>/dev/null
}

brl_lock_take_guarded()
{
    local path
    path="$1"
    if [ -e "$path" ] || [ -L "$path" ]; then
        brl_lock_shape "$path" || return 3
        brl_lock_owner_alive "$path" && return 2
        # All creation, release and stale reaping share the admission guard.
        # No competing process can replace this lock between inspect/unlink.
        rm "$path/owner" && rmdir "$path" || return 3
    fi
    (umask 077; mkdir "$path") || return 3
    ln -T "$BRL_CLAIM" "$path/owner" || return 3
}

brl_lock_acquire()
{
    local role path rc
    role="$1"
    case "$role" in global|request|updater-global) ;; *) return 3 ;; esac
    brl_ram_prepare || return $?
    brl_legacy_locks_clear || return $?
    brl_admission_enter || return $?
    path="$BRL_GLOBAL_LOCK"; rc=0
    case "$role" in
        request) path="$BRL_REQUEST_LOCK" ;;
        global)
            [ ! -e "$BRL_REQUEST_LOCK" ] && [ ! -L "$BRL_REQUEST_LOCK" ] || rc=2 ;;
        updater-global)
            brl_lock_shape "$BRL_REQUEST_LOCK" &&
                cmp -s "$BRL_REQUEST_LOCK/owner" "$BRL_CLAIM" || rc=3 ;;
    esac
    if [ "$rc" -eq 0 ]; then brl_lock_take_guarded "$path" || rc=$?; fi
    brl_admission_leave || return 3
    return "$rc"
}

brl_lock_release()
{
    local path rc
    brl_ram_prepare || return $?
    case "$1" in global|updater-global) path="$BRL_GLOBAL_LOCK" ;; request) path="$BRL_REQUEST_LOCK" ;; *) return 3 ;; esac
    brl_admission_enter || return $?
    rc=0
    if brl_lock_shape "$path" && cmp -s "$path/owner" "$BRL_CLAIM"; then
        rm "$path/owner" && rmdir "$path" || rc=3
    else
        rc=3
    fi
    brl_admission_leave || return 3
    return "$rc"
}
