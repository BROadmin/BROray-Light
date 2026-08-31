#!/opt/bin/ash
. /opt/broray-light/web-new/api/auth-common.sh
broray_api_require_method GET; broray_api_require_session; payload="$(/opt/broray-light/bin/broray-home-snapshot 2>/dev/null || cat /opt/broray-light/run/home-summary.json 2>/dev/null || echo '{}')"; broray_api_success "$payload"
