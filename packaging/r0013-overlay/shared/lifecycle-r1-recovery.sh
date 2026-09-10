#!/opt/bin/ash
# Dead-owner recovery authority. Loaded only from the root-owned sealed new
# app slot; an environment variable is never an authorization mechanism.

brl_recovery_slots_bound()
{
    local root slot key sha files bytes
    brl_r1_receipt_valid || return 1
    root="${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/broray-light"
    for key in source target; do
        if [ "$key" = source ]; then
            slot="$root/releases/1.0.0-r1"
            sha="$(jq -r '.sourceSlotManifestSha256' "$BRL_R1_JOURNAL")"
        else
            slot="$root/releases/2.0.0-r1"
            sha="$(jq -r '.slotManifestSha256' "$BRL_R1_JOURNAL")"
        fi
        brl_r1_directory "$slot" && brl_r1_regular "$slot/APP-SHA256SUMS" &&
            [ "$(sha256sum "$slot/APP-SHA256SUMS" | awk '{print $1}')" = "$sha" ] || return 1
        files="$(awk 'END{print NR-1}' "$slot/APP-SHA256SUMS")"
        bytes="$(find "$slot/app" -type f -exec wc -c {} \; | awk '{s+=$1} END{print s+0}')"
        brl_r1_manifest_valid "$slot" "$files" "$bytes" || return 1
        jq -e --arg id "${slot##*/}" '.product=="BROray-Light" and .releaseId==$id' "$slot/release.json" >/dev/null || return 1
    done
}

brl_recovery_base()
{
    local prefix pid start path current
    brl_recovery_slots_bound || return 1
    prefix="${BRORAY_LIGHT_ROOT_PREFIX:-}"
    ROOT="$prefix/opt/broray-light"
    for path in "$prefix/opt/broray" "$prefix/opt/etc/init.d/S24broray" "$prefix/opt/var/lock/broray/global-operation.lock"; do
        [ ! -e "$path" ] && [ ! -L "$path" ] || return 1
    done
    pid="$(jq -r '.legacyPid' "$BRL_R1_JOURNAL")"
    start="$(jq -r '.legacyStart' "$BRL_R1_JOURNAL")"
    [ "$(brl_process_start "$pid" 2>/dev/null || true)" != "$start" ] || return 2
    current="$(readlink "$ROOT/current")" || return 1
    case "$current" in releases/1.0.0-r1|releases/2.0.0-r1) ;; *) return 1 ;; esac
    BRL_RECOVERY_BOOT="$(cat /proc/sys/kernel/random/boot_id)" || return 1
    printf '%s\n' "$BRL_RECOVERY_BOOT" | grep -Eq '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
}

brl_r1_recovery_authorized()
{
    local start owner phase
    brl_recovery_base || return 1
    start="$(brl_process_start "$$")" || return 1
    jq -e --arg pid "$$" --arg start "$start" --arg boot "$BRL_RECOVERY_BOOT" '
        .recovery.schemaVersion==1 and .recovery.pid==$pid and .recovery.start==$start and
        .recovery.bootId==$boot and .legacyLocks=="cleared"
        ' "$BRL_R1_JOURNAL" >/dev/null || return 1
    owner="BROray-Light:lock/1 $$ $start"
    phase="$(jq -r '.recovery.phase' "$BRL_R1_JOURNAL")"
    case "$phase" in
        admitted|rolling-back|finalizing)
            brl_lock_shape "$BRL_GLOBAL_LOCK" && [ "$(cat "$BRL_GLOBAL_LOCK/owner")" = "$owner" ] ;;
        namespace-restore)
            # The final namespace switch runs under admission after releasing
            # our global lock. No full RAM prepare may recreate the new updater
            # namespace once the old updater's namespace has been restored.
            brl_ram_file_valid "$BRL_ADMISSION" && [ "$(cat "$BRL_ADMISSION")" = "$owner" ] &&
                [ ! -e "$BRL_GLOBAL_LOCK" ] && [ ! -L "$BRL_GLOBAL_LOCK" ] &&
                [ ! -e "$BRL_REQUEST_LOCK" ] && [ ! -L "$BRL_REQUEST_LOCK" ] &&
                [ "$(readlink "$ROOT/current")" = releases/1.0.0-r1 ] ;;
        *) return 1 ;;
    esac
}

brl_recovery_begin()
{
    local start rc
    brl_recovery_base || return $?
    # Only the application namespace is needed for admission. The old updater
    # download namespace can still be unmarked before its first RAM handoff.
    brl_ram_prepare_app && brl_admission_enter || return 1
    rc=0
    [ ! -e "$BRL_REQUEST_LOCK" ] && [ ! -L "$BRL_REQUEST_LOCK" ] || rc=1
    if [ "$rc" -eq 0 ]; then brl_lock_take_guarded "$BRL_GLOBAL_LOCK" || rc=$?; fi
    if [ "$rc" -eq 0 ]; then
        start="$(brl_process_start "$$")" || rc=1
        brl_r1_locks_reconcile_guarded || rc=1
        if [ "$rc" -eq 0 ]; then
            brl_r1_ram_save --arg pid "$$" --arg start "$start" --arg boot "$BRL_RECOVERY_BOOT" \
                '.recovery=((.recovery // {}) + {schemaVersion:1,phase:"admitted",pid:$pid,start:$start,bootId:$boot})' || rc=1
        fi
    fi
    brl_admission_leave || return 1
    [ "$rc" -eq 0 ] || return "$rc"
    brl_r1_recovery_authorized
}

brl_recovery_decide()
{
    local transaction current phase coordinator
    brl_r1_recovery_authorized || return 1
    transaction="${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/var/lib/broray-light-updater/transaction.json"
    current="$(readlink "$ROOT/current")"
    coordinator="$(jq -r '.coordinator.phase // "unstarted"' "$BRL_R1_JOURNAL")"
    if [ ! -e "$transaction" ] && [ ! -L "$transaction" ]; then
        if [ "$current:$coordinator" = releases/2.0.0-r1:activated ]; then
            BRL_RECOVERY_INTENT=finalize
            BRL_RECOVERY_TRANSACTION_SHA=absent
        elif [ "$current" = releases/1.0.0-r1 ] &&
            jq -e '.recovery.intent=="rollback" and .recovery.transactionRetired==true' "$BRL_R1_JOURNAL" >/dev/null; then
            BRL_RECOVERY_INTENT=rollback
            BRL_RECOVERY_TRANSACTION_SHA="$(jq -r '.recovery.transactionSha256' "$BRL_R1_JOURNAL")"
        else return 1
        fi
    else
        brl_r1_regular "$transaction" && [ "$(wc -c < "$transaction")" -le 16384 ] || return 1
        jq -e '.schemaVersion==1 and .previousRelease=="1.0.0-r1" and
            .targetRelease=="2.0.0-r1"' "$transaction" >/dev/null || return 1
        phase="$(jq -r '.phase' "$transaction")"
        case "$phase:$current:$coordinator" in
            committed:releases/2.0.0-r1:activated) BRL_RECOVERY_INTENT=finalize ;;
            target-active:releases/2.0.0-r1:*|target-active:releases/1.0.0-r1:*) BRL_RECOVERY_INTENT=rollback ;;
            rolled-back:releases/1.0.0-r1:restored) BRL_RECOVERY_INTENT=rollback ;;
            *) return 1 ;;
        esac
        BRL_RECOVERY_TRANSACTION_SHA="$(sha256sum "$transaction" | awk '{print $1}')"
    fi
    brl_r1_ram_save --arg intent "$BRL_RECOVERY_INTENT" --arg sha "$BRL_RECOVERY_TRANSACTION_SHA" \
        '.recovery.intent=$intent | .recovery.transactionSha256=$sha'
}

brl_recovery_ram()
{
    local boot directory phase
    brl_r1_recovery_authorized || return 1
    boot="$(jq -r '.legacyBootId' "$BRL_R1_JOURNAL")"
    if [ "$boot" = "$BRL_RECOVERY_BOOT" ]; then
        if jq -e '.snapshotCleanup=="removing" or .snapshotCleanup=="complete"' "$BRL_R1_JOURNAL" >/dev/null; then
            brl_r1_ram_save '.recovery.ramLost=false'; return $?
        fi
        phase="$(jq -r '.ramTransition.phase // "unstarted"' "$BRL_R1_JOURNAL")"
        case "$phase" in
          restored|restoring) brl_r1_ram_bound || return 1 ;;
          *)
            # Promotion checks original work inode/mode/content captured before
            # the first namespace change and exact existing snapshot identities.
            brl_r1_ram_promote || return 1
          ;;
        esac
        brl_r1_ram_save '.recovery.ramLost=false'
    else
        directory="$(jq -r '.ramTransition.directory // empty' "$BRL_R1_JOURNAL")"
        if [ -n "$directory" ]; then
            printf '%s\n' "$directory" | grep -Eq '^broray-light-transition\.[A-Za-z0-9]{6}$' || return 1
            [ ! -e "${BRORAY_LIGHT_ROOT_PREFIX:-}/tmp/$directory" ] &&
                [ ! -L "${BRORAY_LIGHT_ROOT_PREFIX:-}/tmp/$directory" ] || return 1
        fi
        # Application admission is available even when an old S23/recover
        # invocation has recreated its empty, unmarked updater work directory.
        # Do not adopt or overwrite that directory here.
        brl_r1_ram_save '.recovery.ramLost=true'
    fi
}

brl_recovery_stop()
{
    local i
    brl_r1_recovery_authorized && brl_ram_prepare_app || return 1
    brl_service_stop_role daemon && brl_service_stop_role web && brl_service_stop_role auth || return 1
    BRORAY_XRAY_BINARY="$ROOT/runtime/xray"; BRORAY_XRAY_CONFIG="$ROOT/config/config.json"
    if [ -n "$(broray_xray_runtime_pids)" ]; then
        broray_xray_runtime_signal TERM || return 1
        i=0
        while [ -n "$(broray_xray_runtime_pids)" ] && [ "$i" -lt 10 ]; do sleep 1; i=$((i+1)); done
    fi
    [ -z "$(broray_xray_runtime_pids)" ] && brl_legacy_quiesce
}

brl_recovery_lost_trees_restore()
{
    local name source inventory mode inode
    brl_r1_recovery_authorized && [ "$(jq -r '.recovery.ramLost' "$BRL_R1_JOURNAL")" = true ] || return 1
    BRL_TREE_ROOT="$ROOT"
    for name in $(brl_legacy_tree_names); do
        jq -e --arg name "$name" '.runtimeTrees[$name]' "$BRL_R1_JOURNAL" >/dev/null || continue
        source="$ROOT/$name"
        inventory="$(jq -r --arg name "$name" '.runtimeTrees[$name].inventory' "$BRL_R1_JOURNAL")"
        if [ "$(jq -r --arg name "$name" '.runtimeTrees[$name].phase' "$BRL_R1_JOURNAL")" = restored-after-ram-loss ]; then
            if [ -n "$inventory" ]; then
                brl_r1_directory "$source" &&
                    [ "$(stat -c '%d:%i' "$source")" = "$(jq -r --arg name "$name" '.runtimeTrees[$name].lostRestoreId' "$BRL_R1_JOURNAL")" ] || return 1
            else [ ! -e "$source" ] && [ ! -L "$source" ] || return 1
            fi
            continue
        fi
        if [ -L "$source" ]; then
            [ "$(readlink "$source")" = "$BRL_RAM/$name" ] && rm "$source" || return 1
        elif [ -e "$source" ]; then
            # Only original recorded survivors may remain after an interrupted
            # cross-filesystem removal. Never erase an unrecognized object.
            brl_tree_survivors_valid "$name" || return 1
        fi
        if [ -n "$inventory" ] && [ ! -e "$source" ]; then
            mode="$(printf '%s\n' "$inventory" | awk '$1=="D" && $6=="." {print $2}')"
            case "$mode" in 700|755) ;; *) return 1 ;; esac
            (umask 077; mkdir "$source") && chmod "$mode" "$source" || return 1
        fi
        if [ -z "$inventory" ]; then [ ! -e "$source" ] && [ ! -L "$source" ] || return 1; fi
        inode=absent
        [ ! -d "$source" ] || inode="$(stat -c '%d:%i' "$source")"
        brl_r1_ram_save --arg name "$name" --arg id "$inode" \
            '.runtimeTrees[$name].phase="restored-after-ram-loss" | .runtimeTrees[$name].lostRestoreId=$id' || return 1
    done
}

brl_recovery_switch_old()
{
    local staged version candidate inode expected
    brl_r1_recovery_authorized || return 1
    staged="$ROOT/.current.r0013-restored"
    version="$ROOT/config/version"
    candidate="$ROOT/config/.version.r0013-restored"
    brl_r1_regular "$version" && [ "$(stat -c '%h' "$version")" = 1 ] || return 1
    case "$(stat -c '%a' "$version")" in 600|644) ;; *) return 1 ;; esac
    case "$(cat "$version")" in 1.0.0-r1|2.0.0-r1) ;; *) return 1 ;; esac
    brl_r1_ram_save '.recovery.sourceSwitch.phase="prepared"' || return 1
    if [ -e "$staged" ] || [ -L "$staged" ]; then
        [ -L "$staged" ] && [ "$(readlink "$staged")" = releases/1.0.0-r1 ] &&
            [ "$(stat -c '%u' "$staged")" = 0 ] || return 1
        inode="$(stat -c '%d:%i' "$staged")"
        jq -e --arg id "$inode" '.recovery.sourceSwitch.linkId==$id' "$BRL_R1_JOURNAL" >/dev/null || return 1
    elif [ "$(readlink "$ROOT/current")" != releases/1.0.0-r1 ]; then
        ln -s releases/1.0.0-r1 "$staged" || return 1
        inode="$(stat -c '%d:%i' "$staged")"
        brl_r1_ram_save --arg id "$inode" '.recovery.sourceSwitch.linkId=$id' || return 1
    fi
    if [ -L "$staged" ]; then mv -fT "$staged" "$ROOT/current" || return 1; fi
    [ "$(readlink "$ROOT/current")" = releases/1.0.0-r1 ] || return 1
    if [ -e "$candidate" ] || [ -L "$candidate" ]; then
        brl_ram_file_valid "$candidate" && [ "$(stat -c '%h' "$candidate")" = 1 ] || return 1
        inode="$(stat -c '%d:%i' "$candidate")"
        jq -e --arg id "$inode" '.recovery.sourceSwitch.versionId==$id' "$BRL_R1_JOURNAL" >/dev/null || return 1
    elif [ "$(cat "$version")" != 1.0.0-r1 ]; then
        (umask 077; set -C; : > "$candidate") || return 1
        inode="$(stat -c '%d:%i' "$candidate")"
        brl_r1_ram_save --arg id "$inode" '.recovery.sourceSwitch.versionId=$id' || return 1
    fi
    if [ -e "$candidate" ]; then
        printf '1.0.0-r1\n' > "$candidate" && mv -fT "$candidate" "$version" || return 1
    fi
    [ "$(cat "$version")" = 1.0.0-r1 ] &&
        brl_r1_ram_save '.recovery.sourceSwitch.phase="restored"'
}

brl_recovery_remove_recorded_tree()
{
    local tree expected root_id actual row type mode inode size sha relative path
    tree="$1"; expected="$2"; root_id="$3"
    case "$tree" in
        "$BRL_TRANSITION_PRIVATE/runtime-r1/run"|"$BRL_TRANSITION_PRIVATE/runtime-r1/logs"|\
        "$BRL_TRANSITION_PRIVATE/runtime-r1/tmp"|"$BRL_TRANSITION_PRIVATE/runtime-r1/update") ;;
        *) return 1 ;;
    esac
    [ -e "$tree" ] || [ -L "$tree" ] || return 0
    brl_r1_directory "$tree" && [ "$(stat -c '%d:%i' "$tree")" = "$root_id" ] || return 1
    actual="$(brl_tree_inventory "$tree" no)" || return 1
    # Surviving files may be a subset after interrupted cleanup, never extras.
    printf '%s\n' "$actual" | while IFS= read -r row; do
        printf '%s\n' "$expected" | grep -Fqx "$row" || return 1
    done || return 1
    actual="$(brl_tree_inventory "$tree" yes)" || return 1
    printf '%s\n' "$actual" | sort -k6,6r | while read -r type mode inode size sha relative; do
        path="$tree"; [ "$relative" = . ] || path="$tree/$relative"
        [ ! -L "$path" ] && [ "$(stat -c '%u:%a:%d:%i' "$path")" = "0:$mode:$inode" ] || return 1
        case "$type" in
            F) [ -f "$path" ] && [ "$(stat -c '%h' "$path")" = 1 ] &&
                [ "$(sha256sum "$path" | awk '{print $1}')" = "$sha" ] && rm "$path" || return 1 ;;
            D) rmdir "$path" || return 1 ;;
            *) return 1 ;;
        esac
    done
}

brl_recovery_retire_transaction()
{
    local transaction expected
    brl_r1_recovery_authorized || return 1
    transaction="${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/var/lib/broray-light-updater/transaction.json"
    expected="$(jq -r '.recovery.transactionSha256' "$BRL_R1_JOURNAL")"
    if [ "$expected" = absent ]; then [ ! -e "$transaction" ] && [ ! -L "$transaction" ]; return $?; fi
    if [ ! -e "$transaction" ] && [ ! -L "$transaction" ]; then
        [ "$(jq -r '.recovery.transactionRetired // false' "$BRL_R1_JOURNAL")" = true ]; return $?
    fi
    brl_r1_regular "$transaction" && [ "$(stat -c '%h' "$transaction")" = 1 ] &&
        [ "$(sha256sum "$transaction" | awk '{print $1}')" = "$expected" ] || return 1
    brl_r1_ram_save '.recovery.transactionRetired=true' && rm "$transaction"
}

brl_recovery_release_guarded()
{
    brl_lock_shape "$BRL_GLOBAL_LOCK" && cmp -s "$BRL_GLOBAL_LOCK/owner" "$BRL_CLAIM" &&
        rm "$BRL_GLOBAL_LOCK/owner" && rmdir "$BRL_GLOBAL_LOCK"
}

brl_recovery_release()
{
    local rc
    brl_ram_prepare_app && brl_admission_enter || return 1
    rc=0
    brl_recovery_release_guarded || rc=1
    brl_admission_leave || return 1
    return "$rc"
}

brl_recovery_snapshots_cleanup()
{
    local path name expected inode row mode sha private phase
    brl_r1_transition_authorized || return 1
    if [ "$(jq -r '.recovery.ramLost // false' "$BRL_R1_JOURNAL")" = true ]; then
        brl_r1_ram_save '.snapshotCleanup="ram-lost"'; return $?
    fi
    private="$(jq -r '.ramTransition.directory // empty' "$BRL_R1_JOURNAL")"
    [ -n "$private" ] || return 0
    path="${BRORAY_LIGHT_ROOT_PREFIX:-}/tmp/$private"
    case "$private" in broray-light-transition.??????) ;; *) return 1 ;; esac
    if [ ! -e "$path" ] && [ ! -L "$path" ]; then
        [ "$(jq -r '.snapshotCleanup' "$BRL_R1_JOURNAL")" = removing ] ||
            [ "$(jq -r '.snapshotCleanup' "$BRL_R1_JOURNAL")" = complete ] || return 1
        brl_r1_ram_save '.snapshotCleanup="complete"'; return $?
    fi
    if [ "$(jq -r '.snapshotCleanup' "$BRL_R1_JOURNAL")" = removing ] &&
        brl_ram_dir_valid "$path" &&
        [ "$(stat -c '%d:%i' "$path")" = "$(jq -r '.ramTransition.directoryId' "$BRL_R1_JOURNAL")" ] &&
        [ -z "$(find "$path" -mindepth 1 -print)" ]; then
        rmdir "$path" && brl_r1_ram_save '.snapshotCleanup="complete"'; return $?
    fi
    brl_r1_ram_bound || return 1
    # Reject extras before removing any recorded snapshot.
    for path in "$BRL_TRANSITION_PRIVATE"/* "$BRL_TRANSITION_PRIVATE"/.[!.]* "$BRL_TRANSITION_PRIVATE"/..?*; do
        [ -e "$path" ] || [ -L "$path" ] || continue
        case "${path##*/}" in owner|updater-r1|updater-new|runtime-r1) ;; *) return 1 ;; esac
    done
    brl_r1_ram_save '.snapshotCleanup="removing"' || return 1
    path="$BRL_TRANSITION_PRIVATE/runtime-r1"
    if [ -e "$path" ] || [ -L "$path" ]; then
        brl_ram_dir_valid "$path" || return 1
        for private in "$path"/* "$path"/.[!.]* "$path"/..?*; do
            [ -e "$private" ] || [ -L "$private" ] || continue
            case "${private##*/}" in run|logs|tmp|update) ;; *) return 1 ;; esac
        done
        for name in $(brl_legacy_tree_names); do
            expected="$(brl_tree_content "$name")"
            inode="$(jq -r --arg name "$name" '.runtimeTrees[$name].backupId' "$BRL_R1_JOURNAL")"
            brl_recovery_remove_recorded_tree "$path/$name" "$expected" "$inode" || return 1
        done
        rmdir "$path" || return 1
    fi
    path="$BRL_TRANSITION_PRIVATE/updater-r1"
    if [ -e "$path" ] || [ -L "$path" ]; then
        brl_r1_directory "$path" &&
            [ "$(stat -c '%d:%i' "$path")" = "$(jq -r '.ramTransition.oldWorkId' "$BRL_R1_JOURNAL")" ] || return 1
        expected="$(jq -r '.ramTransition.inventory' "$BRL_R1_JOURNAL")"
        for private in "$path"/* "$path"/.[!.]* "$path"/..?*; do
            [ -e "$private" ] || [ -L "$private" ] || continue
            brl_r1_regular "$private" && [ "$(stat -c '%h' "$private")" = 1 ] || return 1
            row="${private##*/} $(stat -c '%d:%i' "$private") $(stat -c '%a' "$private") $(sha256sum "$private" | awk '{print $1}')"
            printf '%s\n' "$expected" | grep -Fqx "$row" || return 1
        done
        for name in app.tar.gz archive.list release.json release.json.minisig; do
            [ ! -e "$path/$name" ] || rm "$path/$name" || return 1
        done
        rmdir "$path" || return 1
    fi
    path="$BRL_TRANSITION_PRIVATE/updater-new"
    if [ -e "$path" ] || [ -L "$path" ]; then
        brl_ram_dir_valid "$path" &&
            [ "$(stat -c '%d:%i' "$path")" = "$(jq -r '.ramTransition.newWorkId' "$BRL_R1_JOURNAL")" ] || return 1
        # The old engine cannot create new-engine work. Unexpected activity
        # here is a conflict, not permission to recursively erase a directory.
        for private in "$path"/* "$path"/.[!.]* "$path"/..?*; do
            [ -e "$private" ] || [ -L "$private" ] || continue
            case "${private##*/}" in owner|work) ;; *) return 1 ;; esac
        done
        if [ -e "$path/work" ] || [ -L "$path/work" ]; then brl_ram_dir_valid "$path/work" && rmdir "$path/work" || return 1; fi
        if [ -e "$path/owner" ] || [ -L "$path/owner" ]; then
            brl_ram_file_valid "$path/owner" && [ "$(cat "$path/owner")" = 'BROray-Light:updater-runtime/1' ] && rm "$path/owner" || return 1
        fi
        rmdir "$path" || return 1
    fi
    rm "$BRL_TRANSITION_PRIVATE/owner" && rmdir "$BRL_TRANSITION_PRIVATE" &&
        brl_r1_ram_save '.snapshotCleanup="complete"'
}

brl_recovery_finalize()
{
    local name
    brl_r1_ram_save '.recovery.phase="finalizing"' && brl_platform_payload &&
        brl_platform_targets_valid new && brl_web_config_bound &&
        brl_web_config_targets_valid new || return 1
    for name in $(brl_legacy_tree_names); do
        jq -e --arg name "$name" '.runtimeTrees[$name].phase=="active"' "$BRL_R1_JOURNAL" >/dev/null &&
            [ -L "$ROOT/$name" ] && [ "$(readlink "$ROOT/$name")" = "$BRL_RAM/$name" ] || return 1
    done
    brl_ram_prepare && brl_recovery_retire_transaction && brl_recovery_snapshots_cleanup || return 1
    brl_r1_ram_save '.coordinator.phase="finalized" | .recovery.phase="finalized"'
}

brl_recovery_old_recover_ancestor()
{
    local engine cursor start raw parent steps
    engine="${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/libexec/broray-light-updater/broray-light-updater.sh"
    brl_r1_regular "$engine" && [ "$(stat -c '%u:%a:%h' "$engine")" = 0:755:1 ] &&
        [ "$(sha256sum "$engine" | awk '{print $1}')" = '773aaf37893ab100e7023d63c8061d8c4763a4d6186844bb3b671d758c145743' ] || return 1
    cursor="$$"; steps=0
    while [ "$steps" -lt 12 ]; do
        start="$(brl_process_start "$cursor")" || return 1
        if tr '\000' '\n' < "/proc/$cursor/cmdline" | awk -v engine="$engine" '
            {a[NR]=$0}
            END {
                shell=(a[1]=="/opt/bin/ash" || a[1]=="/bin/sh" || a[1]=="/bin/dash" || a[1]=="/usr/bin/dash");
                busybox=(a[1]=="/bin/busybox" || a[1]=="/usr/bin/busybox");
                exit !((shell && NR==3 && a[2]==engine && a[3]=="recover") ||
                    (busybox && NR==4 && a[2]=="ash" && a[3]==engine && a[4]=="recover"));
            }'; then
            [ "$(brl_process_start "$cursor")" = "$start" ] || return 1
            BRL_OLD_RECOVER_PID="$cursor"; BRL_OLD_RECOVER_START="$start"
            return 0
        fi
        raw="$(cat "/proc/$cursor/stat" 2>/dev/null)" || return 1
        parent="$(printf '%s\n' "${raw##*) }" | awk '{print $2}')"
        case "$parent" in ''|*[!0-9]*) return 1 ;; esac
        [ "$parent" -gt 1 ] && [ "$parent" != "$cursor" ] || return 1
        cursor="$parent"; steps=$((steps+1))
    done
    return 1
}

brl_recovery_lost_updater_restore()
{
    local path child inode mode
    brl_r1_recovery_authorized && [ "$(jq -r '.recovery.ramLost' "$BRL_R1_JOURNAL")" = true ] || return 1
    path="$BRL_UPDATER_RAM"
    if [ -e "$path" ] || [ -L "$path" ]; then
        if brl_r1_directory "$path" && [ -z "$(find "$path" -mindepth 1 -maxdepth 1 -print)" ]; then
            # Old recover's mkdir -p may leave an unmarked empty survivor.
            # Never adopt, mark or delete that directory: leave its inode and
            # mode intact while returning to r1 under the exact live ancestor.
            [ "$(readlink "$ROOT/current")" = releases/1.0.0-r1 ] &&
                brl_recovery_old_recover_ancestor || return 1
            inode="$(stat -c '%d:%i' "$path")"; mode="$(stat -c '%a' "$path")"
            brl_r1_ram_save --arg pid "$BRL_OLD_RECOVER_PID" --arg start "$BRL_OLD_RECOVER_START" \
                --arg id "$inode" --arg mode "$mode" \
                '.recovery.oldWorkSurvivor={pid:$pid,start:$start,id:$id,mode:$mode,preserved:true}' || return 1
            [ "$(brl_process_start "$BRL_OLD_RECOVER_PID")" = "$BRL_OLD_RECOVER_START" ] &&
                [ "$(stat -c '%u:%a:%d:%i' "$path")" = "0:$mode:$inode" ] &&
                [ -z "$(find "$path" -mindepth 1 -maxdepth 1 -print)" ]
            return $?
        fi
        # Only a private new-engine namespace containing its empty work
        # skeleton can be retired. Unmarked foreign namespaces are refused.
        brl_ram_dir_valid "$path" && brl_ram_file_valid "$path/owner" &&
            [ "$(cat "$path/owner")" = 'BROray-Light:updater-runtime/1' ] || return 1
        for child in "$path"/* "$path"/.[!.]* "$path"/..?*; do
            [ -e "$child" ] || [ -L "$child" ] || continue
            case "${child##*/}" in owner|work) ;; *) return 1 ;; esac
        done
        brl_ram_dir_valid "$path/work" && rmdir "$path/work" && rm "$path/owner" && rmdir "$path" || return 1
    fi
    # Do not initialize the unmarked old namespace. The restored old updater
    # creates its own directory on demand; a bare pre-created path is ambiguous.
}

brl_recovery_rollback()
{
    local path name phase rc
    brl_r1_ram_save '.recovery.phase="rolling-back" | .coordinator.phase="restoring"' &&
        brl_recovery_stop || return 1
    if jq -e '.webConfig' "$BRL_R1_JOURNAL" >/dev/null; then
        brl_web_config_prepare && brl_web_config_restore || return 1
    fi
    if [ "$(jq -r '.recovery.ramLost' "$BRL_R1_JOURNAL")" = true ]; then
        brl_recovery_lost_trees_restore || return 1
    elif jq -e '.runtimeTrees|type=="object" and length==4' "$BRL_R1_JOURNAL" >/dev/null; then
        phase="$(jq -r '.ramTransition.phase' "$BRL_R1_JOURNAL")"
        if [ "$phase" = restored ] || [ "$phase" = restoring ]; then
            for name in $(brl_legacy_tree_names); do brl_tree_copy_complete "$name" "$ROOT/$name" old || return 1; done
        else brl_tree_restore || return 1
        fi
    fi
    brl_platform_payload && brl_platform_targets_valid mixed || return 1
    # Keep the S24 recovery entry until all other durable state is coherent.
    for path in $(brl_platform_paths); do
        [ "$path" = opt/etc/init.d/S24broray-light ] || brl_platform_replace "$path" r1 || return 1
    done
    brl_recovery_switch_old && brl_admission_enter || return 1
    rc=0
    brl_recovery_release_guarded && brl_r1_ram_save '.recovery.phase="namespace-restore"' || rc=1
    if [ "$rc" -eq 0 ]; then
        if [ "$(jq -r '.recovery.ramLost' "$BRL_R1_JOURNAL")" = true ]; then
            brl_recovery_lost_updater_restore || rc=1
        else brl_r1_ram_restore || rc=1
        fi
    fi
    if [ "$rc" -eq 0 ]; then
        brl_recovery_retire_transaction && brl_recovery_snapshots_cleanup &&
            brl_platform_replace opt/etc/init.d/S24broray-light r1 &&
            brl_platform_targets_valid old &&
            brl_r1_ram_save '.platform.phase="restored" | .coordinator.phase="restored" | .recovery.phase="restored"' || rc=1
    fi
    brl_admission_leave || return 1
    [ "$rc" -eq 0 ] || return 1
    "${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/etc/init.d/S24broray-light" start || return 1
    return 10
}

brl_recovery_run()
(
    # Recovery owns a fresh process-wide operation fence. Its exit cleanup
    # never initializes the updater namespace after restoring old r1 paths.
    trap 'if [ -n "${BRL_CLAIM:-}" ]; then brl_admission_leave || true; fi
          if [ -n "${BRL_GLOBAL_LOCK:-}" ] && brl_lock_shape "$BRL_GLOBAL_LOCK" &&
             [ "$(cat "$BRL_GLOBAL_LOCK/owner")" = "BROray-Light:lock/1 $$ $(brl_process_start "$$")" ]; then
              brl_recovery_release || true
          fi' EXIT
    brl_recovery_begin && brl_recovery_decide && brl_recovery_ram || exit 1
    case "$BRL_RECOVERY_INTENT" in
        finalize) brl_recovery_finalize ;;
        rollback) brl_recovery_rollback ;;
        *) exit 1 ;;
    esac
)
