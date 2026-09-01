#!/opt/bin/ash

. /opt/broray-light/web-new/api/auth-common.sh
. /opt/broray-light/lib/web-request-body.sh
. /opt/broray-light/lib/xray-web-operation.sh

broray_api_require_method POST
broray_api_require_session

body_file="/opt/broray-light/tmp/xray-web-update.$$.json"
trap 'rm -f "$body_file"' EXIT
mkdir -p /opt/broray-light/tmp
broray_web_request_body_to_file "$body_file" 4096 ||
    broray_api_error "400 Bad Request" "REQUEST_BODY_INVALID" "Некорректное тело запроса."

mode="$(jq -r '.mode // "update"' "$body_file" 2>/dev/null)" ||
    broray_api_error "400 Bad Request" "REQUEST_JSON_INVALID" "Ожидается JSON-объект."

case "$mode" in
    update)
        operation=broray_xray_web_update
        operation_label="Обновление"
        ;;
    reinstall)
        operation=broray_xray_web_reinstall
        operation_label="Переустановка"
        ;;
    *)
        broray_api_error "400 Bad Request" "XRAY_MODE_INVALID" "Разрешены только обновление или переустановка Xray."
        ;;
esac

if payload="$($operation 2>&1)"; then
    broray_api_success "$(jq -n --arg mode "$mode" --arg message "$payload" '{started:true,mode:$mode,message:$message}')"
else
    broray_api_error "500 Internal Server Error" "XRAY_INSTALL_FAILED" "$operation_label Xray завершилась ошибкой." "$payload"
fi
