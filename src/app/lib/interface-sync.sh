#!/opt/bin/ash

BRORAY_BASE="${BRORAY_BASE:-/opt/broray-light}"
BRORAY_INTERFACE="${BRORAY_INTERFACE:-Proxy0}"
BRORAY_ACTIVE_SERVER_FILE="$BRORAY_BASE/config/active-server"
BRORAY_SERVERS="$BRORAY_BASE/servers"
BRORAY_PROXY_CONVERGENCE_ATTEMPTS="${BRORAY_PROXY_CONVERGENCE_ATTEMPTS:-10}"
BRORAY_PROXY_CONVERGENCE_DELAY="${BRORAY_PROXY_CONVERGENCE_DELAY:-1}"

broray_interface_active_server_id()
{
    local server_id

    [ -s "$BRORAY_ACTIVE_SERVER_FILE" ] && [ ! -L "$BRORAY_ACTIVE_SERVER_FILE" ] || return 1
    server_id="$(sed -n '1p' "$BRORAY_ACTIVE_SERVER_FILE" | tr -d '\r\n')"
    case "$server_id" in ''|*/*|*'..'*) return 1 ;; esac
    printf '%s\n' "$server_id"
}

broray_interface_active_server_name()
{
    local server_id server_file server_name

    server_id="$(broray_interface_active_server_id)" || return 1
    server_file="$BRORAY_SERVERS/$server_id.json"
    [ -f "$server_file" ] && [ ! -L "$server_file" ] || return 1
    server_name="$(jq -r '
      if ((.name|type)=="string" and .name!="") then .name
      elif ((.id|type)=="string" and .id!="") then .id
      else "" end
    ' "$server_file" 2>/dev/null)" || return 1
    server_name="$(printf '%s' "$server_name" | tr '\r\n\t' '   ' |
      sed -e 's/[[:space:]][[:space:]]*/ /g' -e 's/^ //' -e 's/ $//' -e 's/["\\;|&`$<>]//g')"
    [ -n "$server_name" ] || return 1
    printf '%s\n' "$server_name"
}

broray_interface_expected_description()
{
    local server_name description

    server_name="$(broray_interface_active_server_name 2>/dev/null || true)"
    if [ -z "$server_name" ]; then
        printf '%s\n' 'BROray-Light'
        return 0
    fi
    description="BROray-Light - $server_name"
    broray_interface_description_value_valid "$description" || return 1
    printf '%s\n' "$description"
}

broray_interface_set_description()
{
    local description command_text

    description="$1"
    command_text="$(broray_interface_description_command "$description")" || return 1
    broray_interface_ndmc_stage description "$command_text"
}

broray_interface_sync_wait_exact()
{
    local name host port description attempt

    name="$1"
    host="$2"
    port="$3"
    description="$4"
    attempt=0
    while [ "$attempt" -lt "$BRORAY_PROXY_CONVERGENCE_ATTEMPTS" ]; do
        attempt=$((attempt + 1))
        if broray_interface_source_exact running "$name" "$host" "$port" "$description" &&
           broray_interface_source_exact startup "$name" "$host" "$port" "$description" &&
           broray_interface_runtime_ready "$description"; then
            return 0
        fi
        [ "$attempt" -ge "$BRORAY_PROXY_CONVERGENCE_ATTEMPTS" ] || sleep "$BRORAY_PROXY_CONVERGENCE_DELAY"
    done
    return 1
}

broray_interface_sync_description()
{
    local name host port old_description expected failure rollback_command

    broray_interface_require_write_policy || return 1
    name="$(broray_interface_owner_name 2>/dev/null || true)"
    [ -n "$name" ] || {
        printf '%s\n' 'BRORAY_PROXY_ERROR:PROXY_DELETE_AUTHORITY_REFUSED:description sync требует полный BROray-Light receipt' >&2
        return 1
    }
    BRORAY_INTERFACE="$name"
    export BRORAY_INTERFACE
    broray_interface_require_owned "$name" || return 1
    host="$(jq -r '.upstream.host' "$BRORAY_INTERFACE_OWNER_FILE")" || return 1
    port="$(jq -r '.upstream.port' "$BRORAY_INTERFACE_OWNER_FILE")" || return 1
    old_description="$(jq -r '.description' "$BRORAY_INTERFACE_OWNER_FILE")" || return 1
    expected="$(broray_interface_expected_description)" || return 1
    if [ "$old_description" = "$expected" ]; then
        printf '%s\n' 'Синхронизация не требуется'
        return 0
    fi

    failure=''
    broray_interface_set_description "$expected" || failure=description
    [ -n "$failure" ] || sleep "${BRORAY_PROXY_CONFIG_SETTLE_DELAY:-5}"
    [ -n "$failure" ] || broray_interface_ndmc_stage save 'system configuration save' || failure=save
    [ -n "$failure" ] || broray_interface_sync_wait_exact "$name" "$host" "$port" "$expected" || failure=convergence-timeout
    if [ -n "$failure" ]; then
        rollback_command="$(broray_interface_description_command "$old_description")" || return 1
        if broray_interface_ndmc_stage rollback-description \
             "$rollback_command" &&
           broray_interface_ndmc_stage rollback-save 'system configuration save' &&
           broray_interface_sync_wait_exact "$name" "$host" "$port" "$old_description"; then
            printf 'BRORAY_PROXY_SYNC_ROLLBACK=PASS failedStage=%s\n' "$failure" >&2
        else
            printf 'BRORAY_PROXY_ERROR:PROXY_RECOVERY_REQUIRED:description rollback не доказан failedStage=%s\n' "$failure" >&2
        fi
        return 1
    fi
    BRORAY_PROXY_HOST="$host"
    BRORAY_PROXY_PORT="$port"
    export BRORAY_PROXY_HOST BRORAY_PROXY_PORT
    broray_interface_owner_write "$name" description-synced "$expected" || return 1
    printf '%s\n' 'Описание интерфейса синхронизировано и подтверждено exact receipt'
}
