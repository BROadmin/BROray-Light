#!/opt/bin/ash
. /opt/broray-light/web-new/api/servers/common.sh
broray_api_require_method POST
broray_api_require_session
broray_servers_api_lock check

body_file="/opt/broray-light/tmp/servers-check-body.$$.json"
check_result_file="/opt/broray-light/tmp/servers-check-result.$$.json"
trap 'rm -f "$body_file" "$check_result_file"; command -v broray_operation_lock_release >/dev/null 2>&1 && broray_operation_lock_release' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
broray_servers_api_read_body_to_file "$body_file"
body_json="$(cat "$body_file")"
rm -f "$body_file"

server_id="$(
    broray_servers_api_body_field "$body_json" id
)"

# A failed reachability probe is a completed observation, not an API failure.
# broray_server_check deliberately returns the probe status after persisting and
# printing its JSON result. Normalize only a fresh, schema-valid result for the
# requested server; configuration, validation and probe-execution failures stay
# fail-closed through broray_servers_api_run.
broray_servers_api_check_completed()
{
    check_server_id="$1"
    check_rc=0

    : >"$check_result_file"
    broray_server_check \
        "$check_server_id" \
        manual \
        >"$check_result_file" || check_rc=$?

    if jq -e \
        --arg serverId "$check_server_id" '
            type == "object" and
            .serverId == $serverId and
            ((.success | type) == "boolean") and
            ((.checkedAt | type) == "string") and
            ((.checkedAt | length) > 0)
        ' "$check_result_file" >/dev/null 2>&1
    then
        cat "$check_result_file"
        return 0
    fi

    [ "$check_rc" -ne 0 ] || check_rc=1
    return "$check_rc"
}

broray_servers_api_run \
    broray_servers_api_check_completed \
    "$server_id"
