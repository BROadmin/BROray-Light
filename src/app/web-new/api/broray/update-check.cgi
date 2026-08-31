#!/opt/bin/ash
. /opt/broray-light/web-new/api/broray/updater-api-common.sh
broray_api_require_method GET; broray_api_require_session; broray_light_updater_available || broray_api_error "503 Service Unavailable" "UPDATER_UNAVAILABLE" "Обновитель BROray-Light недоступен."; if payload="$($BRORAY_LIGHT_UPDATER check --json 2>&1)"; then broray_api_success "$payload"; else broray_api_error "502 Bad Gateway" "UPDATE_CHECK_FAILED" "Проверка обновления не выполнена." "$payload"; fi
