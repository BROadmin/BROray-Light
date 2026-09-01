#!/opt/bin/ash

BRORAY_BASE="${BRORAY_BASE:-${BRORAY_ROOT:-/opt/broray-light}}"
. "$BRORAY_BASE/lib/util.sh"
. "$BRORAY_BASE/lib/server.sh"
. "$BRORAY_BASE/lib/server-config-generator.sh"
. "$BRORAY_BASE/lib/server-xray-manager.sh"

BRORAY_CHECK_STATE="${BRORAY_CHECK_STATE:-$BRORAY_BASE/run/server-checks}"
BRORAY_PROBE="${BRORAY_PROBE:-$BRORAY_BASE/bin/broray-server-probe}"
BRORAY_AUTO_SWITCH_CONFIG="${BRORAY_AUTO_SWITCH_CONFIG:-$BRORAY_BASE/config/system/server-auto-switch.json}"

broray_server_check_path()
{
    broray_server_validate_id "$1"
    printf '%s/%s.json\n' "$BRORAY_CHECK_STATE" "$1"
}

broray_server_summary()
{
    mkdir -p "$BRORAY_SERVERS" "$BRORAY_CHECK_STATE" "$BRORAY_BASE/tmp"
    active="$(cat "$BRORAY_ACTIVE_SERVER_FILE" 2>/dev/null || true)"
    tmp="$BRORAY_BASE/tmp/server-summary.$$.jsonl"
    : > "$tmp"
    for f in "$BRORAY_SERVERS"/*.json; do
        [ -f "$f" ] || continue
        broray_server_validate "$f" || continue
        id="$(jq -r .id "$f")"
        c="$(broray_server_check_path "$id")"
        if [ -f "$c" ]; then
            jq -n --slurpfile s "$f" --slurpfile c "$c" --arg active "$active" \
                '($s[0])+{active:($s[0].id==$active),lastCheck:$c[0]}' >> "$tmp"
        else
            jq -n --slurpfile s "$f" --arg active "$active" \
                '($s[0])+{active:($s[0].id==$active),lastCheck:null}' >> "$tmp"
        fi
    done
    jq -s --arg active "$active" \
        '{schemaVersion:1,activeServerId:(if $active=="" then null else $active end),servers:.,count:length}' \
        "$tmp"
    rm -f "$tmp"
}

broray_server_details()
{
    id="$1"
    broray_server_exists "$id" || broray_die "сервер не найден"
    f="$(broray_server_path "$id")"
    c="$(broray_server_check_path "$id")"
    if [ -f "$c" ]; then
        jq -n --slurpfile s "$f" --slurpfile c "$c" '($s[0])+{lastCheck:$c[0]}'
    else
        jq -n --slurpfile s "$f" '($s[0])+{lastCheck:null}'
    fi
}

broray_server_check()
{
    id="$1"
    broray_server_exists "$id" || broray_die "сервер не найден"
    mkdir -p "$BRORAY_CHECK_STATE"
    cfg="$(broray_generate_server_config "$id")"
    tmp="$(broray_server_check_path "$id").$$"
    rc=0
    "$BRORAY_PROBE" "$cfg" "$id" > "$tmp" || rc=$?
    rm -f "$cfg"
    jq -e . "$tmp" >/dev/null 2>&1 || {
        rm -f "$tmp"
        broray_die "пробник вернул некорректный JSON"
    }
    chmod 600 "$tmp"
    mv "$tmp" "$(broray_server_check_path "$id")"
    cat "$(broray_server_check_path "$id")"
    return "$rc"
}

broray_server_activate()
{
    id="$1"
    broray_server_exists "$id" || broray_die "сервер не найден"
    broray_xray_apply_server "$id"
    broray_server_details "$id"
}

broray_server_delete_safe()
{
    id="$1"
    active="$(cat "$BRORAY_ACTIVE_SERVER_FILE" 2>/dev/null || true)"
    [ "$id" != "$active" ] || broray_die "нельзя удалить активный сервер"
    f="$(broray_server_path "$id")"
    [ -f "$f" ] || broray_die "сервер не найден"

    mkdir -p "$BRORAY_BASE/tmp"
    server_backup="$BRORAY_BASE/tmp/server-delete.$$.json"
    failover_tmp=""

    if [ -f "$BRORAY_AUTO_SWITCH_CONFIG" ]; then
        failover_tmp="$BRORAY_AUTO_SWITCH_CONFIG.$$"
        jq --arg id "$id" '
            .orderedServerIds = ((.orderedServerIds // []) | map(select(. != $id))) |
            .excludedServerIds = ((.excludedServerIds // []) | map(select(. != $id)))
        ' "$BRORAY_AUTO_SWITCH_CONFIG" > "$failover_tmp" || {
            rm -f "$failover_tmp"
            broray_die "не удалось подготовить настройки автопереключения"
        }
        chmod 600 "$failover_tmp" || {
            rm -f "$failover_tmp"
            broray_die "не удалось защитить настройки автопереключения"
        }
    fi

    mv "$f" "$server_backup" || {
        rm -f "$failover_tmp"
        broray_die "не удалось подготовить удаление сервера"
    }

    if [ -n "$failover_tmp" ] && ! mv "$failover_tmp" "$BRORAY_AUTO_SWITCH_CONFIG"; then
        mv "$server_backup" "$f" >/dev/null 2>&1 || true
        rm -f "$failover_tmp"
        broray_die "не удалось сохранить настройки автопереключения"
    fi

    rm -f "$server_backup" "$(broray_server_check_path "$id")"
    jq -n --arg id "$id" '{deleted:true,id:$id,failoverReferencesPruned:true}'
}
