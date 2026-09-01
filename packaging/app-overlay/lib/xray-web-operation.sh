#!/opt/bin/ash

BRORAY_ROOT="${BRORAY_ROOT:-/opt/broray-light}"
. "$BRORAY_ROOT/lib/operation-lock.sh"
. "$BRORAY_ROOT/lib/xray-control.sh"
. "$BRORAY_ROOT/lib/xray-update.sh"

broray_xray_web_install()
{
    install_mode="${1:-update}"
    case "$install_mode" in
        update|reinstall) ;;
        *) return 4 ;;
    esac

    lock_rc=0
    broray_operation_lock_acquire "xray-$install_mode" || lock_rc=$?
    [ "$lock_rc" -eq 0 ] || return "$lock_rc"
    (
        trap 'broray_operation_lock_release >/dev/null 2>&1 || true' EXIT
        (broray_xray_update_install "$install_mode")
    )
}

broray_xray_web_update()
{
    broray_xray_web_install update
}

broray_xray_web_reinstall()
{
    broray_xray_web_install reinstall
}
