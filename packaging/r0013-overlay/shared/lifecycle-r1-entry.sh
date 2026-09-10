#!/opt/bin/ash
# Live r1 transition coordinator. No environment variable grants authority:
# every nested entry rechecks the recorded legacy PID/start/locks and sealed slot.

brl_live_load()
{
    local prefix slot helper path parent
    prefix="${BRORAY_LIGHT_ROOT_PREFIX:-}"
    case "$prefix" in *[!A-Za-z0-9/_.-]*|*/../*|*/..|*/./*|*/.|*//*|*/) return 1 ;; esac
    case "$prefix" in ''|/*) ;; *) return 1 ;; esac
    ROOT="$prefix/opt/broray-light"
    slot="$ROOT/releases/2.0.0-r1/app"
    for parent in "$ROOT" "$ROOT/releases" "$ROOT/releases/2.0.0-r1" "$slot" "$slot/lib" \
        "$slot/share" "$slot/share/lifecycle" "$slot/share/lifecycle/helpers"; do
        [ -d "$parent" ] && [ ! -L "$parent" ] || return 1
        case "$(stat -c '%u:%a' "$parent")" in 0:700|0:755) ;; *) return 1 ;; esac
    done
    for helper in runtime-ram.sh lifecycle-r1-admission.sh lifecycle-r1-journal.sh \
        lifecycle-r1-ram.sh lifecycle-r1-platform.sh lifecycle-r1-web-config.sh \
        service-process.sh lifecycle-r1-runtime-trees.sh lifecycle-r1-recovery.sh; do
        path="$slot/share/lifecycle/helpers/$helper"
        [ -f "$path" ] && [ ! -L "$path" ] && [ "$(stat -c '%u:%a:%h' "$path")" = 0:644:1 ] || return 1
        . "$path" || return 1
    done
    path="$slot/lib/xray-process.sh"
    [ -f "$path" ] && [ ! -L "$path" ] || return 1
    case "$(stat -c '%u:%a:%h' "$path")" in 0:644:1|0:755:1) ;; *) return 1 ;; esac
    . "$path" || return 1
    brl_r1_journal_path
}

brl_live_transaction()
{
    local path current
    brl_platform_payload || return 1
    path="${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/var/lib/broray-light-updater/transaction.json"
    brl_r1_regular "$path" && jq -e '.schemaVersion==1 and
      .previousRelease=="1.0.0-r1" and .targetRelease=="2.0.0-r1" and
      (.phase=="target-active" or .phase=="rolled-back")' "$path" >/dev/null || return 1
    current="$(readlink "$ROOT/current")"
    case "$current" in releases/1.0.0-r1|releases/2.0.0-r1) ;; *) return 1 ;; esac
}

brl_live_stop_new()
{
    local i
    brl_live_transaction && brl_ram_prepare || return 1
    brl_service_stop_role daemon && brl_service_stop_role web && brl_service_stop_role auth || return 1
    BRORAY_XRAY_BINARY="$ROOT/runtime/xray"; BRORAY_XRAY_CONFIG="$ROOT/config/config.json"
    if [ -n "$(broray_xray_runtime_pids)" ]; then
        broray_xray_runtime_signal TERM || return 1
        i=0
        while [ -n "$(broray_xray_runtime_pids)" ] && [ "$i" -lt 10 ]; do sleep 1; i=$((i+1)); done
    fi
    [ -z "$(broray_xray_runtime_pids)" ]
}

brl_live_targets_active()
{
    local name
    brl_live_transaction && brl_r1_ram_bound && brl_ram_prepare &&
        brl_platform_targets_valid new && brl_web_config_bound &&
        brl_web_config_targets_valid new || return 1
    for name in $(brl_legacy_tree_names); do
        jq -e --arg name "$name" '.runtimeTrees[$name].phase=="active"' "$BRL_R1_JOURNAL" >/dev/null &&
            [ -L "$ROOT/$name" ] && [ "$(readlink "$ROOT/$name")" = "$BRL_RAM/$name" ] || return 1
    done
}

brl_live_restore()
{
    local name source expected
    brl_live_transaction || return 1
    brl_r1_ram_save '.coordinator.phase="restoring"' || return 1
    # No new service can exist before all runtime aliases were installed.
    if jq -e '.runtimeTrees|to_entries|any(.value.phase=="active" or .value.phase=="copied")' "$BRL_R1_JOURNAL" >/dev/null 2>&1; then
        brl_live_stop_new || return 1
    fi
    if jq -e '.webConfig' "$BRL_R1_JOURNAL" >/dev/null; then
        brl_web_config_prepare && brl_web_config_restore || return 1
    fi
    if jq -e '.platform' "$BRL_R1_JOURNAL" >/dev/null; then brl_platform_restore || return 1; fi
    if jq -e '.runtimeTrees|to_entries|any(.value.phase!="planned")' "$BRL_R1_JOURNAL" >/dev/null 2>&1; then
        brl_tree_restore || return 1
    else
        # An incomplete admission/backup has not deleted any original file.
        # Prove the complete originals before returning to the old service.
        for name in $(brl_legacy_tree_names); do
            if jq -e --arg name "$name" '.runtimeTrees[$name]' "$BRL_R1_JOURNAL" >/dev/null; then
                source="$ROOT/$name"
                expected="$(jq -r --arg name "$name" '.runtimeTrees[$name].inventory' "$BRL_R1_JOURNAL")"
                if [ -n "$expected" ]; then [ "$(brl_tree_inventory "$source" yes)" = "$expected" ] || return 1
                else [ ! -e "$source" ] && [ ! -L "$source" ] || return 1
                fi
            fi
        done
    fi
    if jq -e '.ramTransition' "$BRL_R1_JOURNAL" >/dev/null; then brl_r1_ram_restore || return 1; fi
    brl_r1_ram_save '.coordinator.phase="restored"'
}

brl_live_prepare()
{
    local phase
    if ! brl_r1_receipt_valid; then brl_r1_transition_record || return 1; fi
    brl_live_transaction || return 1
    [ "$(readlink "$ROOT/current")" = releases/2.0.0-r1 ] || return 1
    phase="$(jq -r '.coordinator.phase // "unstarted"' "$BRL_R1_JOURNAL")"
    case "$phase" in
        starting|activated)
            # Inner S24 startup and legacy health checks must not recopy live
            # sessions or stop a newly started process.
            brl_live_targets_active; return $? ;;
        unstarted|prepared) ;;
        *) return 1 ;;
    esac
    brl_r1_ram_save '.coordinator={schemaVersion:1,phase:"prepared"}' || return 1
    if brl_platform_recovery_anchor && brl_r1_ram_promote && brl_tree_prepare_all && brl_web_config_prepare &&
        brl_tree_promote && brl_web_config_activate && brl_platform_activate &&
        brl_r1_ram_save '.coordinator.phase="starting"' &&
        "${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/etc/init.d/S24broray-light" start &&
        brl_live_targets_active && brl_r1_ram_save '.coordinator.phase="activated"'; then
        return 10 # Outer, cached r1 S24 may now observe the new RAM-backed PIDs.
    fi
    brl_live_restore || { brl_r1_refuse LIVE_ROLLBACK_FAILED; return 1; }
    return 1
}

brl_r1_entry()
{
    local kind action current
    kind="$1"; action="${2:-}"
    brl_live_load || return 1
    if brl_r1_receipt_valid &&
        [ "$(brl_process_start "$(jq -r '.legacyPid' "$BRL_R1_JOURNAL")" 2>/dev/null || true)" != "$(jq -r '.legacyStart' "$BRL_R1_JOURNAL")" ]; then
        brl_recovery_run; return $?
    fi
    case "$kind" in
        prepare) brl_live_prepare; return $? ;;
        service)
            [ "$action" != recover ] || return 2
            brl_live_transaction || return 1
            current="$(readlink "$ROOT/current")"
            if [ "$current" = releases/1.0.0-r1 ]; then
                case "$action" in
                    stop) brl_live_stop_new || return 1; return 10 ;;
                    start)
                        brl_live_restore || return 1
                        exec "${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/etc/init.d/S24broray-light" start ;;
                    *) return 1 ;;
                esac
            fi
            case "$action" in
                stop) brl_live_stop_new || return 1; return 10 ;;
                start|status) brl_live_targets_active ;;
                *) return 1 ;;
            esac ;;
        *) return 1 ;;
    esac
}
