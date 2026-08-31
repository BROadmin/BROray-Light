#!/opt/bin/ash
. /opt/broray-light/web-new/api/auth-common.sh
broray_api_require_method GET; broray_api_require_session; broray_api_success "$(/opt/broray-light/bin/broray-system info)"
