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

broray_subscriptions_api_parse_error()
{
    broray_subscriptions_api_error_line="$1"
    BRORAY_SUBSCRIPTIONS_API_ERROR_CODE=""
    BRORAY_SUBSCRIPTIONS_API_ERROR_MESSAGE=""
    BRORAY_SUBSCRIPTIONS_API_ERROR_STATUS="400 Bad Request"

    case "$broray_subscriptions_api_error_line" in
        BRORAY_ERROR:*:*) ;;
        *) return 1 ;;
    esac

    broray_subscriptions_api_error_value="${broray_subscriptions_api_error_line#BRORAY_ERROR:}"
    BRORAY_SUBSCRIPTIONS_API_ERROR_CODE="${broray_subscriptions_api_error_value%%:*}"
    BRORAY_SUBSCRIPTIONS_API_ERROR_MESSAGE="${broray_subscriptions_api_error_value#*:}"
    case "$BRORAY_SUBSCRIPTIONS_API_ERROR_CODE" in
        ''|*[!A-Z0-9_]*) return 1 ;;
    esac
    [ -n "$BRORAY_SUBSCRIPTIONS_API_ERROR_MESSAGE" ] || return 1

    case "$BRORAY_SUBSCRIPTIONS_API_ERROR_CODE" in
        ACTIVE_SERVER_CONFLICT|SERVER_SYNC_BUSY|SUBSCRIPTION_LOCKED)
            BRORAY_SUBSCRIPTIONS_API_ERROR_STATUS="409 Conflict"
            ;;
        SUBSCRIPTION_NOT_FOUND)
            BRORAY_SUBSCRIPTIONS_API_ERROR_STATUS="404 Not Found"
            ;;
    esac
    return 0
}

broray_subscriptions_api_run()
{
    broray_subscriptions_api_operation="$1"
    broray_subscriptions_api_output_file="/opt/broray-light/tmp/sub-api.$$.json"
    broray_subscriptions_api_error_file="$broray_subscriptions_api_output_file.err"
    mkdir -p /opt/broray-light/tmp
    # Isolate service globals from the wrapper's capture paths.
    if ( "$@" ) >"$broray_subscriptions_api_output_file" 2>"$broray_subscriptions_api_error_file"; then
        case "$broray_subscriptions_api_operation" in
            broray_subscription_create|broray_subscription_update|broray_subscription_update_settings)
                if ! /opt/broray-light/bin/broray-subscriptions deduplicate >/dev/null 2>"$broray_subscriptions_api_error_file"; then
                    broray_subscriptions_api_message="$(tail -c 1200 "$broray_subscriptions_api_error_file")"
                    rm -f "$broray_subscriptions_api_output_file" "$broray_subscriptions_api_error_file"
                    broray_api_error "500 Internal Server Error" "SERVER_DEDUPLICATION_FAILED" "Подписка сохранена, но устранить дубли серверов не удалось." "$broray_subscriptions_api_message"
                fi
                ;;
        esac
        broray_subscriptions_api_payload="$(cat "$broray_subscriptions_api_output_file")"
        [ -n "$broray_subscriptions_api_payload" ] || broray_subscriptions_api_payload='{}'
        if ! printf '%s\n' "$broray_subscriptions_api_payload" | jq -e . >/dev/null 2>&1; then
            rm -f "$broray_subscriptions_api_output_file" "$broray_subscriptions_api_error_file"
            broray_api_error "500 Internal Server Error" "SUBSCRIPTION_RESPONSE_INVALID" "Операция выполнена, но вернула некорректный результат."
        fi
        rm -f "$broray_subscriptions_api_output_file" "$broray_subscriptions_api_error_file"
        broray_api_success "$broray_subscriptions_api_payload"
    else
        broray_subscriptions_api_error_line="$(tail -n 1 "$broray_subscriptions_api_error_file" | tr -d '\r')"
        rm -f "$broray_subscriptions_api_output_file" "$broray_subscriptions_api_error_file"
        if broray_subscriptions_api_parse_error "$broray_subscriptions_api_error_line"; then
            broray_api_error \
                "$BRORAY_SUBSCRIPTIONS_API_ERROR_STATUS" \
                "$BRORAY_SUBSCRIPTIONS_API_ERROR_CODE" \
                "$BRORAY_SUBSCRIPTIONS_API_ERROR_MESSAGE"
        fi
        broray_api_error \
            "400 Bad Request" \
            "SUBSCRIPTION_OPERATION_FAILED" \
            "Операция с подпиской завершилась ошибкой."
    fi
}
