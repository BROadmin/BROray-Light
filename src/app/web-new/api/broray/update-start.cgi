#!/opt/bin/ash
. /opt/broray-light/web-new/api/broray/updater-api-common.sh
broray_api_require_method POST; broray_api_require_session; broray_light_updater_available || broray_api_error "503 Service Unavailable" "UPDATER_UNAVAILABLE" "Обновитель BROray-Light недоступен."; if payload="$($BRORAY_LIGHT_UPDATER update --json 2>&1)"; then broray_api_success "$payload"; else broray_api_error "500 Internal Server Error" "UPDATE_FAILED" "Обновление BROray-Light завершилось ошибкой." "$payload"; fi
