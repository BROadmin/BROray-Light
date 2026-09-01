#!/opt/bin/ash
. /opt/broray-light/web-new/api/auth-common.sh
. /opt/broray-light/lib/operation-lock.sh
. /opt/broray-light/lib/xray-control.sh
. /opt/broray-light/lib/xray-update.sh

broray_api_require_method POST
broray_api_require_session
lock_rc=0
broray_operation_lock_acquire xray-update-check || lock_rc=$?
case "$lock_rc" in
    0) trap 'broray_operation_lock_release >/dev/null 2>&1 || true' EXIT ;;
    2) broray_api_error "409 Conflict" "OPERATION_BUSY" "Другая операция уже выполняется." ;;
    *) broray_api_error "500 Internal Server Error" "GLOBAL_LOCK_FAILED" "Не удалось получить блокировку." ;;
esac

output="/opt/broray-light/tmp/xray-update-check.$$.json"
trap 'rm -f "$output"; broray_operation_lock_release >/dev/null 2>&1 || true' EXIT
if broray_xray_update_check >"$output" && jq -e '.success == true' "$output" >/dev/null 2>&1; then
    broray_api_success "$(cat "$output")"
    exit 0
fi
details="$(jq -r '.error // .message // empty' "$output" 2>/dev/null)"
broray_api_error "502 Bad Gateway" "XRAY_UPDATE_CHECK_FAILED" "Проверка обновления Xray завершилась ошибкой." "$details"
