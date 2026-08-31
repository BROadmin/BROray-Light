#!/opt/bin/ash
. /opt/broray-light/web-new/api/auth-common.sh
broray_api_require_method GET; broray_api_require_session; state=/opt/var/lib/broray-light-updater/state.json; [ -r "$state" ] && payload="$(cat "$state")" || payload='{"state":"idle"}'; broray_api_success "$payload"
