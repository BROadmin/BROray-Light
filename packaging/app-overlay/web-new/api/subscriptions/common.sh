#!/opt/bin/ash

. /opt/broray-light/web-new/api/auth-common.sh
. /opt/broray-light/lib/web-request-body.sh
. /opt/broray-light/lib/subscription-service.sh
. /opt/broray-light/lib/operation-lock.sh

broray_subscriptions_api_lock()
{
    rc=0
    broray_operation_lock_acquire "subscriptions:${1:-action}" || rc=$?
    case "$rc" in
        0) trap 'broray_operation_lock_release >/dev/null 2>&1 || true' EXIT ;;
        2) broray_api_error "409 Conflict" "OPERATION_BUSY" "Другая операция уже выполняется." ;;
        *) broray_api_error "500 Internal Server Error" "GLOBAL_LOCK_FAILED" "Не удалось получить блокировку." ;;
    esac
}

broray_subscriptions_api_read_body_to_file()
{
    body_target="$1"
    rc=0
    broray_web_request_body_to_file "$body_target" 65536 || rc=$?
    [ "$rc" -eq 0 ] || broray_api_error "400 Bad Request" "REQUEST_BODY_INVALID" "Некорректное тело запроса."
    jq -e 'type=="object"' "$body_target" >/dev/null 2>&1 ||
        broray_api_error "400 Bad Request" "REQUEST_JSON_INVALID" "Ожидается JSON-объект."
}

broray_subscriptions_api_query()
{
    printf '%s' "${QUERY_STRING:-}" | tr '&' '\n' | awk -F= -v name="$1" '$1==name{sub(/^[^=]*=/,"");print;exit}'
}

broray_subscriptions_api_run()
{
    operation_name="$1"
    output_file="/opt/broray-light/tmp/sub-api.$$.json"
    error_file="$output_file.err"
    mkdir -p /opt/broray-light/tmp
    if "$@" >"$output_file" 2>"$error_file"; then
        case "$operation_name" in
            broray_subscription_create|broray_subscription_update|broray_subscription_update_settings)
                if ! /opt/broray-light/bin/broray-subscriptions deduplicate >/dev/null 2>"$error_file"; then
                    message="$(tail -c 1200 "$error_file")"
                    rm -f "$output_file" "$error_file"
                    broray_api_error "500 Internal Server Error" "SERVER_DEDUPLICATION_FAILED" "Подписка сохранена, но устранить дубли серверов не удалось." "$message"
                fi
                ;;
        esac
        payload="$(cat "$output_file")"
        rm -f "$output_file" "$error_file"
        broray_api_success "$payload"
    else
        message="$(tail -c 1200 "$error_file")"
        rm -f "$output_file" "$error_file"
        broray_api_error "400 Bad Request" "SUBSCRIPTION_OPERATION_FAILED" "Операция с подпиской завершилась ошибкой." "$message"
    fi
}
