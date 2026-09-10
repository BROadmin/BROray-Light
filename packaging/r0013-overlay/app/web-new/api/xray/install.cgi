#!/opt/bin/ash
. /opt/broray-light/web-new/api/auth-common.sh
. /opt/broray-light/lib/web-request-body.sh
. /opt/broray-light/lib/xray-web-operation.sh

broray_api_require_method POST
broray_api_require_session

umask 077
body_file="$(mktemp /tmp/broray-light-xray-request.XXXXXX)" ||
    broray_api_error "500 Internal Server Error" "REQUEST_STORAGE_FAILED" "Не удалось создать временный запрос."
trap 'rm -f "$body_file"' EXIT
broray_web_request_body_to_file "$body_file" 4096 ||
    broray_api_error "400 Bad Request" "REQUEST_BODY_INVALID" "Некорректное тело запроса."
broray_xray_install_request_valid "$body_file" ||
    broray_api_error "400 Bad Request" "XRAY_SELECTION_INVALID" "Ожидается выбранная версия Xray и явные подтверждения."

if payload="$(broray_xray_web_install install "$body_file")"; then
    broray_api_success "$payload"
else
    details="$(printf '%s' "$payload" | jq -r '.error // empty' 2>/dev/null)"
    broray_api_error "409 Conflict" "XRAY_INSTALL_REFUSED" "Установка выбранной версии Xray не выполнена." "$details"
fi
