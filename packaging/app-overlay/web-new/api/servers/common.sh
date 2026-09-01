#!/opt/bin/ash
. /opt/broray-light/web-new/api/auth-common.sh
. /opt/broray-light/lib/web-request-body.sh
. /opt/broray-light/lib/server-service.sh
. /opt/broray-light/lib/server-import.sh
. /opt/broray-light/lib/operation-lock.sh

broray_servers_api_lock(){ rc=0; broray_operation_lock_acquire "servers:${1:-action}" || rc=$?; case "$rc" in 0) trap 'broray_operation_lock_release >/dev/null 2>&1 || true' EXIT;; 2) broray_api_error "409 Conflict" "OPERATION_BUSY" "Другая операция уже выполняется.";; *) broray_api_error "500 Internal Server Error" "GLOBAL_LOCK_FAILED" "Не удалось получить блокировку.";; esac; }
broray_servers_api_read_body_to_file(){ f="$1"; rc=0; broray_web_request_body_to_file "$f" 65536 || rc=$?; [ "$rc" -eq 0 ] || broray_api_error "400 Bad Request" "REQUEST_BODY_INVALID" "Некорректное тело запроса."; jq -e 'type=="object"' "$f" >/dev/null 2>&1 || broray_api_error "400 Bad Request" "REQUEST_JSON_INVALID" "Ожидается JSON-объект."; }
broray_servers_api_body_field(){ printf '%s' "$1" | jq -r --arg f "$2" '.[$f]//empty'; }

broray_servers_api_parse_error()
{
    broray_servers_api_error_line="$1"
    BRORAY_SERVERS_API_ERROR_CODE=""
    BRORAY_SERVERS_API_ERROR_MESSAGE=""
    BRORAY_SERVERS_API_ERROR_STATUS="400 Bad Request"

    case "$broray_servers_api_error_line" in
        "Ошибка: нельзя удалить активный сервер")
            BRORAY_SERVERS_API_ERROR_CODE="ACTIVE_SERVER_CONFLICT"
            BRORAY_SERVERS_API_ERROR_MESSAGE="Активный сервер удалить нельзя. Сначала активируйте другой сервер."
            BRORAY_SERVERS_API_ERROR_STATUS="409 Conflict"
            ;;
        "Ошибка: проверка соединения после активации не пройдена")
            BRORAY_SERVERS_API_ERROR_CODE="SERVER_UNREACHABLE"
            BRORAY_SERVERS_API_ERROR_MESSAGE="Сервер недоступен. Активация отменена, предыдущая конфигурация восстановлена."
            BRORAY_SERVERS_API_ERROR_STATUS="422 Unprocessable Entity"
            ;;
        "Ошибка: Xray отклонил конфигурацию сервера"|"Ошибка: некорректная запись VLESS-сервера")
            BRORAY_SERVERS_API_ERROR_CODE="SERVER_CONFIG_INVALID"
            BRORAY_SERVERS_API_ERROR_MESSAGE="Xray отклонил конфигурацию этого VLESS-сервера."
            BRORAY_SERVERS_API_ERROR_STATUS="422 Unprocessable Entity"
            ;;
        "Ошибка: сервер не найден"|Ошибка:\ сервер\ *\ не\ найден)
            BRORAY_SERVERS_API_ERROR_CODE="SERVER_NOT_FOUND"
            BRORAY_SERVERS_API_ERROR_MESSAGE="Сервер не найден. Обновите страницу и повторите действие."
            BRORAY_SERVERS_API_ERROR_STATUS="404 Not Found"
            ;;
        "Ошибка: такой VLESS-сервер уже добавлен"|"Ошибка: сервер уже существует")
            BRORAY_SERVERS_API_ERROR_CODE="SERVER_DUPLICATE"
            BRORAY_SERVERS_API_ERROR_MESSAGE="Такой VLESS-сервер уже добавлен."
            BRORAY_SERVERS_API_ERROR_STATUS="409 Conflict"
            ;;
        "Ошибка: BROray-Light поддерживает только VLESS"|\
        "Ошибка: поддерживаются только ссылки vless://"|\
        "Ошибка: не указана ссылка VLESS"|\
        "Ошибка: не найден UUID"|\
        Ошибка:\ неподдерживаемый\ транспорт\ VLESS:*|\
        Ошибка:\ неподдерживаемая\ защита\ VLESS:*|\
        Ошибка:\ неподдерживаемый\ режим\ VLESS\ flow:*|\
        "Ошибка: VLESS flow поддерживается только для TCP/RAW + REALITY")
            BRORAY_SERVERS_API_ERROR_CODE="INVALID_VLESS"
            BRORAY_SERVERS_API_ERROR_MESSAGE="Некорректная или неподдерживаемая VLESS-ссылка."
            ;;
        *)
            return 1
            ;;
    esac
    return 0
}

broray_servers_api_run()
{
    broray_servers_api_output_file="/opt/broray-light/tmp/servers-api.$$.json"
    broray_servers_api_error_file="$broray_servers_api_output_file.err"
    mkdir -p /opt/broray-light/tmp

    # Service functions use global ash variables. Run them in a subshell so an
    # internal variable named `out` cannot replace the CGI capture path.
    if ( "$@" ) >"$broray_servers_api_output_file" 2>"$broray_servers_api_error_file"; then
        broray_servers_api_payload="$(cat "$broray_servers_api_output_file")"
        [ -n "$broray_servers_api_payload" ] || broray_servers_api_payload='{}'
        if ! printf '%s\n' "$broray_servers_api_payload" | jq -e . >/dev/null 2>&1; then
            rm -f "$broray_servers_api_output_file" "$broray_servers_api_error_file"
            broray_api_error "500 Internal Server Error" "SERVER_RESPONSE_INVALID" "Операция выполнена, но вернула некорректный результат."
        fi
        rm -f "$broray_servers_api_output_file" "$broray_servers_api_error_file"
        broray_api_success "$broray_servers_api_payload"
    else
        broray_servers_api_error_line="$(tail -n 1 "$broray_servers_api_error_file" | tr -d '\r')"
        rm -f "$broray_servers_api_output_file" "$broray_servers_api_error_file"
        if broray_servers_api_parse_error "$broray_servers_api_error_line"; then
            broray_api_error \
                "$BRORAY_SERVERS_API_ERROR_STATUS" \
                "$BRORAY_SERVERS_API_ERROR_CODE" \
                "$BRORAY_SERVERS_API_ERROR_MESSAGE"
        fi
        broray_api_error \
            "400 Bad Request" \
            "SERVER_OPERATION_FAILED" \
            "Операция с сервером завершилась ошибкой."
    fi
}
