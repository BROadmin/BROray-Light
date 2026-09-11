#!/opt/bin/ash
# Router scratch paths are fixed product namespaces, not caller preferences.
# This library is sourced before application code that reads/writes runtime data.
brl_runtime_environment()
{
    local prefix root helper path
    prefix="${BRORAY_LIGHT_ROOT_PREFIX:-}"
    case "$prefix" in *[!A-Za-z0-9/_.-]*) return 1 ;; esac
    case "$prefix" in ''|/*) ;; *) return 1 ;; esac
    case "$prefix" in */../*|*/..|*/./*|*/.|*//*|*/) return 1 ;; esac
    # CGI may discard its parent's PATH. Resolve Entware utilities before the
    # first ownership check; firmware /bin need not provide stat at all.
    # A non-empty prefix is an explicit isolated-root harness, not the router.
    if [ -z "$prefix" ]; then
        case "${PATH:-}" in
            /opt/bin:/opt/sbin:*) ;;
            *) PATH="/opt/bin:/opt/sbin:${PATH:-/usr/bin:/bin}" ;;
        esac
        export PATH
    fi
    root="$prefix/opt/broray-light"
    [ "${BRORAY_ROOT:-$root}" = "$root" ] && [ "${BRORAY_BASE:-$root}" = "$root" ] || return 1
    for path in "$prefix/opt/broray" "$prefix/opt/etc/init.d/S24broray" \
                "$prefix/opt/var/lock/broray/global-operation.lock"; do
        [ ! -e "$path" ] && [ ! -L "$path" ] || return 1
    done
    helper="$root/lib/runtime-ram.sh"
    [ -f "$helper" ] && [ ! -L "$helper" ] || return 1
    case "$(stat -c '%u:%a' "$helper")" in 0:644|0:755) ;; *) return 1 ;; esac
    . "$helper" || return 1
    brl_ram_prepare || return 1
    brl_ram_child "$BRL_RAM/update" || return 1
    # opkg children can inherit the installer's invocation-owned TMPDIR. It is
    # removed after installation, while our daemon and its children keep running.
    # Bind scratch to the already validated product RAM directory instead.
    TMPDIR="$BRL_RAM/tmp"
    export TMPDIR
    BRORAY_ROOT="$root"; BRORAY_BASE="$root"
    BRORAY_INTERFACE_LAST_EVIDENCE="$BRL_RAM/run/interface-last-command.json"
    BRORAY_INTERFACE_FAILURE_EVIDENCE="$BRL_RAM/run/interface-last-failure.json"
    BRORAY_KEENETIC_STATUS_FILE="$BRL_RAM/run/keenetic-status.json"
    BRORAY_CHECK_STATE="$BRL_RAM/run/server-checks"
    BRORAY_SUB_RUN="$BRL_RAM/run/subscriptions"
    BRORAY_SUB_LOG="$BRL_RAM/logs/subscriptions.log"
    BRORAY_XRAY_STATUS_CACHE_FILE="$BRL_RAM/run/xray-status-cache.json"
    BRORAY_XRAY_UPDATE_TMP_ROOT="$BRL_RAM/tmp"
    BRORAY_XRAY_RELEASE_CACHE="$BRL_RAM/cache/xray-releases.json"
    BRORAY_XRAY_DOWNLOAD_ROOT="$BRL_RAM/tmp/xray-download"
    BRORAY_XRAY_UPDATE_WORK="$BRL_RAM/tmp/xray-update"
    BRORAY_NATIVE_AUTH_BASE="$root"
    BRORAY_NATIVE_AUTH_DIR="$BRL_RAM/run/web-new/native-auth"
    BRORAY_NATIVE_AUTH_RUNTIME="$BRORAY_NATIVE_AUTH_DIR/broray-ndm-auth-nginx"
    BRORAY_NATIVE_AUTH_CONFIG="$BRORAY_NATIVE_AUTH_DIR/nginx.conf"
    BRORAY_NATIVE_AUTH_PIDFILE="$BRORAY_NATIVE_AUTH_DIR/nginx.pid"
    BRORAY_NATIVE_AUTH_LOG="$BRORAY_NATIVE_AUTH_DIR/nginx.log"
    export BRORAY_ROOT BRORAY_BASE BRORAY_INTERFACE_LAST_EVIDENCE BRORAY_INTERFACE_FAILURE_EVIDENCE
    export BRORAY_KEENETIC_STATUS_FILE BRORAY_CHECK_STATE BRORAY_SUB_RUN BRORAY_SUB_LOG
    export BRORAY_XRAY_STATUS_CACHE_FILE BRORAY_XRAY_UPDATE_TMP_ROOT BRORAY_XRAY_RELEASE_CACHE
    export BRORAY_XRAY_DOWNLOAD_ROOT BRORAY_XRAY_UPDATE_WORK BRORAY_NATIVE_AUTH_BASE BRORAY_NATIVE_AUTH_DIR
    export BRORAY_NATIVE_AUTH_RUNTIME BRORAY_NATIVE_AUTH_CONFIG BRORAY_NATIVE_AUTH_PIDFILE BRORAY_NATIVE_AUTH_LOG
}

brl_runtime_environment || {
    printf 'BRORAY_LIGHT_RUNTIME_REFUSED: protected RAM environment is unavailable or ambiguous.\n' >&2
    return 1
}
