#!/opt/bin/ash
# Requires runtime-ram.sh, lifecycle-r1-admission.sh and lifecycle-r1-journal.sh.
# Only the admitted old updater's descendants may perform this live handoff.
# The receipt is durable; both old and new downloaded work stay on tmpfs.

brl_r1_transition_live()
{
    local prefix pid start engine path
    brl_r1_receipt_valid || return 1
    prefix="${BRORAY_LIGHT_ROOT_PREFIX:-}"
    pid="$(jq -r '.legacyPid' "$BRL_R1_JOURNAL")"
    start="$(jq -r '.legacyStart' "$BRL_R1_JOURNAL")"
    engine="$prefix/opt/libexec/broray-light-updater/broray-light-updater.sh"
    [ "$(brl_process_start "$pid")" = "$start" ] &&
        brl_r1_owner_argv "$pid" "$engine" && brl_r1_owner_ancestor "$pid" || {
        brl_r1_refuse NOT_LIVE_TRANSITION_CHILD; return 1;
    }
    for path in "$prefix/opt/broray" "$prefix/opt/etc/init.d/S24broray" \
                "$prefix/opt/var/lock/broray/global-operation.lock"; do
        [ ! -e "$path" ] && [ ! -L "$path" ] || return 1
    done
    [ "$(jq -r '.legacyLocks' "$BRL_R1_JOURNAL")" = owned ] || return 1
    brl_r1_lock_shape "$prefix/opt/var/lock/broray-light-updater/request.lock" &&
        brl_r1_lock_shape "$prefix/opt/var/lock/broray-light/global-operation.lock" || return 1
    brl_r1_recorded_lock_safe "$prefix/opt/var/lock/broray-light-updater/request.lock" \
        "$(jq -c '.requestIds' "$BRL_R1_JOURNAL")" "$pid" &&
    brl_r1_recorded_lock_safe "$prefix/opt/var/lock/broray-light/global-operation.lock" \
        "$(jq -c '.globalIds' "$BRL_R1_JOURNAL")" "$pid"
}

brl_r1_ram_base()
{
    BRL_TRANSITION_TMP="${BRORAY_LIGHT_ROOT_PREFIX:-}/tmp"
    [ "$(id -u)" = 0 ] && [ -d "$BRL_TRANSITION_TMP" ] && [ ! -L "$BRL_TRANSITION_TMP" ] &&
        [ "$(stat -c '%u:%a' "$BRL_TRANSITION_TMP")" = 0:1777 ] || return 1
    case "$(stat -f -c '%T' "$BRL_TRANSITION_TMP")" in tmpfs|ramfs) ;; *) return 1 ;; esac
    BRL_TRANSITION_WORK="$BRL_TRANSITION_TMP/broray-light-updater"
}

brl_r1_work_inventory()
{
    local path name count
    brl_r1_directory "$1" || return 1
    count="$(find "$1" -mindepth 1 -maxdepth 1 -print | wc -l | tr -d ' ')"
    [ "$count" = 4 ] || return 1
    for name in app.tar.gz archive.list release.json release.json.minisig; do
        path="$1/$name"
        brl_r1_regular "$path" || return 1
        printf '%s %s %s %s\n' "$name" "$(stat -c '%d:%i' "$path")" \
            "$(stat -c '%a' "$path")" "$(sha256sum "$path" | awk '{print $1}')"
    done
}

brl_r1_ram_save()
{
    local staged
    # The only callers are serialized descendants of the exact legacy update.
    # Do not overwrite an interrupted adjacent receipt candidate.
    staged="$BRL_R1_JOURNAL.$$.new"
    [ ! -e "$staged" ] && [ ! -L "$staged" ] || return 1
    (umask 077; set -C; jq "$@" "$BRL_R1_JOURNAL" > "$staged") || return 1
    brl_ram_file_valid "$staged" && mv -fT "$staged" "$BRL_R1_JOURNAL"
}

brl_r1_ram_bound()
{
    local name private_id
    brl_r1_receipt_valid && brl_r1_ram_base || return 1
    jq -e '.ramTransition | .schemaVersion==1 and
      (.directory|type=="string" and test("^broray-light-transition\\.[A-Za-z0-9]{6}$")) and
      (.directoryId|type=="string" and test("^[0-9]+:[0-9]+$")) and
      (.oldWorkId|type=="string" and test("^[0-9]+:[0-9]+$")) and
      (.oldWorkMode=="700" or .oldWorkMode=="755") and
      (.inventory|type=="string" and length>0) and
      (.phase=="prepared" or .phase=="old-moved" or .phase=="ready" or .phase=="restoring" or .phase=="restored")
      ' "$BRL_R1_JOURNAL" >/dev/null 2>&1 || return 1
    name="$(jq -r '.ramTransition.directory' "$BRL_R1_JOURNAL")"
    BRL_TRANSITION_PRIVATE="$BRL_TRANSITION_TMP/$name"
    private_id="$(jq -r '.ramTransition.directoryId' "$BRL_R1_JOURNAL")"
    brl_ram_dir_valid "$BRL_TRANSITION_PRIVATE" &&
        [ "$(stat -c '%d:%i' "$BRL_TRANSITION_PRIVATE")" = "$private_id" ] &&
        brl_ram_file_valid "$BRL_TRANSITION_PRIVATE/owner" &&
        [ "$(cat "$BRL_TRANSITION_PRIVATE/owner")" = 'BROray-Light:r1-transition/1' ]
}

brl_r1_old_work_bound()
{
    brl_r1_directory "$1" &&
        [ "$(stat -c '%d:%i' "$1")" = "$(jq -r '.ramTransition.oldWorkId' "$BRL_R1_JOURNAL")" ] &&
        [ "$(stat -c '%a' "$1")" = "$(jq -r '.ramTransition.oldWorkMode' "$BRL_R1_JOURNAL")" ] &&
        [ "$(brl_r1_work_inventory "$1")" = "$(jq -r '.ramTransition.inventory' "$BRL_R1_JOURNAL")" ]
}

brl_r1_ram_promote()
{
    local inventory old_id old_mode private_id phase new_id
    brl_r1_ram_base || { brl_r1_refuse RAM_BASE; return 1; }
    brl_r1_journal_path || return 1
    if ! brl_r1_receipt_valid || ! jq -e '.ramTransition' "$BRL_R1_JOURNAL" >/dev/null 2>&1; then
        brl_r1_transition_record || return 1
        inventory="$(brl_r1_work_inventory "$BRL_TRANSITION_WORK")" || { brl_r1_refuse LEGACY_WORK_SHAPE; return 1; }
        old_id="$(stat -c '%d:%i' "$BRL_TRANSITION_WORK")"
        old_mode="$(stat -c '%a' "$BRL_TRANSITION_WORK")"
        BRL_TRANSITION_PRIVATE="$(umask 077; mktemp -d "$BRL_TRANSITION_TMP/broray-light-transition.XXXXXX")" || return 1
        (umask 077; set -C; printf 'BROray-Light:r1-transition/1\n' > "$BRL_TRANSITION_PRIVATE/owner") || return 1
        private_id="$(stat -c '%d:%i' "$BRL_TRANSITION_PRIVATE")"
        brl_r1_ram_save --arg inventory "$inventory" --arg id "$old_id" --arg mode "$old_mode" \
            --arg directory "${BRL_TRANSITION_PRIVATE##*/}" --arg privateId "$private_id" \
            '.ramTransition={schemaVersion:1,phase:"prepared",directory:$directory,directoryId:$privateId,
              oldWorkId:$id,oldWorkMode:$mode,inventory:$inventory}' || return 1
    fi
    brl_r1_transition_live && brl_r1_ram_bound || { brl_r1_refuse RAM_RECEIPT; return 1; }
    phase="$(jq -r '.ramTransition.phase' "$BRL_R1_JOURNAL")"
    case "$phase" in prepared|old-moved|ready) ;; *) brl_r1_refuse RAM_PHASE; return 1 ;; esac
    if [ "$phase" = prepared ]; then
        # Resume after rename-before-receipt only if the exact old inode moved.
        if [ -e "$BRL_TRANSITION_WORK" ] || [ -L "$BRL_TRANSITION_WORK" ]; then
            brl_r1_old_work_bound "$BRL_TRANSITION_WORK" &&
                [ ! -e "$BRL_TRANSITION_PRIVATE/updater-r1" ] && [ ! -L "$BRL_TRANSITION_PRIVATE/updater-r1" ] || return 1
            [ "$(stat -c '%d' "$BRL_TRANSITION_WORK")" = "$(stat -c '%d' "$BRL_TRANSITION_PRIVATE")" ] || return 1
            mv -T "$BRL_TRANSITION_WORK" "$BRL_TRANSITION_PRIVATE/updater-r1" || return 1
        fi
        brl_r1_old_work_bound "$BRL_TRANSITION_PRIVATE/updater-r1" || return 1
        brl_r1_ram_save '.ramTransition.phase="old-moved"' || return 1
    fi
    brl_r1_old_work_bound "$BRL_TRANSITION_PRIVATE/updater-r1" || return 1
    brl_ram_prepare || { brl_r1_refuse RAM_NAMESPACE; return 1; }
    new_id="$(stat -c '%d:%i' "$BRL_TRANSITION_WORK")"
    if [ "$phase" = ready ]; then
        [ "$new_id" = "$(jq -r '.ramTransition.newWorkId' "$BRL_R1_JOURNAL")" ] || return 1
    else
        brl_r1_ram_save --arg id "$new_id" '.ramTransition.phase="ready" | .ramTransition.newWorkId=$id' || return 1
    fi
}

brl_r1_ram_restore()
{
    local phase new_id path
    brl_r1_transition_live && brl_r1_ram_bound || { brl_r1_refuse RAM_RECEIPT; return 1; }
    phase="$(jq -r '.ramTransition.phase' "$BRL_R1_JOURNAL")"
    if [ "$phase" = restored ]; then brl_r1_old_work_bound "$BRL_TRANSITION_WORK"; return $?; fi
    case "$phase" in ready|restoring|old-moved|prepared) ;; *) return 1 ;; esac
    if brl_r1_old_work_bound "$BRL_TRANSITION_WORK" 2>/dev/null; then
        [ ! -e "$BRL_TRANSITION_PRIVATE/updater-r1" ] && [ ! -L "$BRL_TRANSITION_PRIVATE/updater-r1" ] || return 1
        brl_r1_ram_save '.ramTransition.phase="restored"'; return $?
    fi
    brl_r1_old_work_bound "$BRL_TRANSITION_PRIVATE/updater-r1" || { brl_r1_refuse OLD_RAM_IDENTITY; return 1; }
    if [ -e "$BRL_TRANSITION_WORK" ] || [ -L "$BRL_TRANSITION_WORK" ]; then
        [ "$phase" = ready ] || { brl_r1_refuse RAM_PHASE; return 1; }
        new_id="$(jq -r '.ramTransition.newWorkId' "$BRL_R1_JOURNAL")"
        brl_ram_dir_valid "$BRL_TRANSITION_WORK" &&
            [ "$(stat -c '%d:%i' "$BRL_TRANSITION_WORK")" = "$new_id" ] &&
            brl_ram_file_valid "$BRL_TRANSITION_WORK/owner" &&
            [ "$(cat "$BRL_TRANSITION_WORK/owner")" = 'BROray-Light:updater-runtime/1' ] || return 1
        # A new live operation cannot be evicted even during rollback.
        for path in "$BRL_TRANSITION_WORK/request.lock" "$BRL_TRANSITION_TMP/broray-light/run/locks/admission" \
                    "$BRL_TRANSITION_TMP/broray-light/run/locks/global-operation.lock"; do
            [ ! -e "$path" ] && [ ! -L "$path" ] || return 1
        done
        [ ! -e "$BRL_TRANSITION_PRIVATE/updater-new" ] && [ ! -L "$BRL_TRANSITION_PRIVATE/updater-new" ] || return 1
        # Preserve rather than recursively delete all new RAM data.
        mv -T "$BRL_TRANSITION_WORK" "$BRL_TRANSITION_PRIVATE/updater-new" || return 1
    fi
    brl_r1_ram_save '.ramTransition.phase="restoring"' || return 1
    [ ! -e "$BRL_TRANSITION_WORK" ] && [ ! -L "$BRL_TRANSITION_WORK" ] || return 1
    mv -T "$BRL_TRANSITION_PRIVATE/updater-r1" "$BRL_TRANSITION_WORK" || return 1
    brl_r1_old_work_bound "$BRL_TRANSITION_WORK" && brl_r1_ram_save '.ramTransition.phase="restored"'
}
