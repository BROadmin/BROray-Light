#!/opt/bin/ash
. /opt/broray-light/web-new/api/subscriptions/common.sh
broray_api_require_session
subscription_id="$(broray_subscriptions_api_query id)"
case "${REQUEST_METHOD:-}" in
    GET)
        broray_subscriptions_api_run broray_subscription_get "$subscription_id"
        ;;
    POST)
        broray_subscriptions_api_lock settings
        settings_body="/opt/broray-light/tmp/subscription-settings-api.$$.json"
        trap 'rm -f "$settings_body"; broray_operation_lock_release >/dev/null 2>&1 || true' EXIT
        broray_subscriptions_api_read_body_to_file "$settings_body"
        broray_subscriptions_api_run \
            broray_subscription_update_settings "$subscription_id" "$settings_body"
        ;;
    *)
        broray_api_error "405 Method Not Allowed" "METHOD_NOT_ALLOWED" "Метод запроса не поддерживается."
        ;;
esac
