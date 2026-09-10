#!/opt/bin/ash
BRORAY_ROOT="${BRORAY_ROOT:-/opt/broray-light}"
. "$BRORAY_ROOT/lib/xray-control.sh"
. "$BRORAY_ROOT/lib/xray-update.sh"

broray_xray_web_install() {
    case "${1:-}" in update|reinstall|install) ;; *) return 4 ;; esac
    broray_xray_install_dispatch "$@"
}
broray_xray_web_update() { broray_xray_web_install update; }
broray_xray_web_reinstall() { broray_xray_web_install reinstall; }
