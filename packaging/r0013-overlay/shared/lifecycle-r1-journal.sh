#!/opt/bin/ash
# Requires runtime-ram.sh and lifecycle-r1-admission.sh definitions.
# This is a durable ownership receipt, never a persistent operational lock.

brl_r1_journal_path()
{
    local prefix parent
    prefix="${BRORAY_LIGHT_ROOT_PREFIX:-}"
    case "$prefix" in ''|/*) ;; *) return 1 ;; esac
    case "$prefix" in */../*|*/..|*/./*|*/.|*//*|*/) return 1 ;; esac
    parent="$prefix/opt/var/lib/broray-light-updater"
    brl_r1_directory "$parent" || return 1
    BRL_R1_JOURNAL="$parent/legacy-transition.json"
}

brl_r1_lock_ids()
{
    stat -c '%d:%i' "$1" "$1/pid" "$1/operation" | jq -Rsc 'split("\n") | map(select(length>0))'
}

brl_r1_receipt_valid()
{
    brl_r1_journal_path && brl_ram_file_valid "$BRL_R1_JOURNAL" || return 1
    jq -e '
      .schemaVersion==1 and .product=="BROray-Light" and
      .sourceRelease=="1.0.0-r1" and .targetRelease=="2.0.0-r1" and
      (.legacyLocks=="owned" or .legacyLocks=="cleared") and
      (.legacyPid|type=="string" and test("^[0-9]+$")) and
      (.legacyPid|tonumber)>1 and
      (.legacyStart|type=="string" and test("^[0-9]+$")) and
      .engineSha256=="773aaf37893ab100e7023d63c8061d8c4763a4d6186844bb3b671d758c145743" and
      (.slotManifestSha256|type=="string" and test("^[0-9a-f]{64}$")) and
      (.sourceSlotManifestSha256|type=="string" and test("^[0-9a-f]{64}$")) and
      (.legacyBootId|type=="string" and test("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")) and
      (.legacyWork.id|type=="string" and test("^[0-9]+:[0-9]+$")) and
      (.legacyWork.mode=="700" or .legacyWork.mode=="755") and
      (.legacyWork.inventory|type=="string" and length>0) and
      ([.requestIds,.globalIds] | all(type=="array" and length==3 and all(type=="string" and test("^[0-9]+:[0-9]+$"))))
    ' "$BRL_R1_JOURNAL" >/dev/null 2>&1
}

brl_r1_transition_record()
{
    local prefix request global request_ids global_ids slot_sha source_sha source_slot boot staged
    local work inventory work_id work_mode
    brl_r1_transition_admitted || return 1
    brl_r1_journal_path || return 1
    prefix="${BRORAY_LIGHT_ROOT_PREFIX:-}"
    request="$prefix/opt/var/lock/broray-light-updater/request.lock"
    global="$prefix/opt/var/lock/broray-light/global-operation.lock"
    request_ids="$(brl_r1_lock_ids "$request")" || return 1
    global_ids="$(brl_r1_lock_ids "$global")" || return 1
    slot_sha="$(sha256sum "$prefix/opt/broray-light/current/APP-SHA256SUMS" | awk '{print $1}')"
    source_slot="$prefix/opt/broray-light/releases/1.0.0-r1"
    brl_r1_manifest_valid "$source_slot" "$(awk 'END{print NR-1}' "$source_slot/APP-SHA256SUMS")" \
        "$(find "$source_slot/app" -type f -exec wc -c {} \; | awk '{s+=$1} END{print s+0}')" || return 1
    source_sha="$(sha256sum "$source_slot/APP-SHA256SUMS" | awk '{print $1}')"
    boot="$(cat /proc/sys/kernel/random/boot_id)" || return 1
    printf '%s\n' "$boot" | grep -Eq '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' || return 1
    work="$prefix/tmp/broray-light-updater"
    inventory="$(brl_r1_work_inventory "$work")" || { brl_r1_refuse LEGACY_WORK_SHAPE; return 1; }
    work_id="$(stat -c '%d:%i' "$work")"; work_mode="$(stat -c '%a' "$work")"
    if [ -e "$BRL_R1_JOURNAL" ] || [ -L "$BRL_R1_JOURNAL" ]; then
        brl_r1_receipt_valid && jq -e --arg pid "$BRL_LEGACY_UPDATER_PID" --arg start "$BRL_LEGACY_UPDATER_START" \
            --argjson request "$request_ids" --argjson global "$global_ids" --arg sha "$slot_sha" --arg source "$source_sha" --arg boot "$boot" \
            --arg workId "$work_id" --arg workMode "$work_mode" --arg inventory "$inventory" '
            .legacyLocks=="owned" and .legacyPid==$pid and .legacyStart==$start and
            .requestIds==$request and .globalIds==$global and .slotManifestSha256==$sha and
            .sourceSlotManifestSha256==$source and .legacyBootId==$boot and
            .legacyWork=={id:$workId,mode:$workMode,inventory:$inventory}
            ' "$BRL_R1_JOURNAL" >/dev/null 2>&1 || { brl_r1_refuse RECEIPT_COLLISION; return 1; }
        return 0
    fi
    staged="$BRL_R1_JOURNAL.$$.new"
    [ ! -e "$staged" ] && [ ! -L "$staged" ] || return 1
    (umask 077; set -C; jq -n --arg pid "$BRL_LEGACY_UPDATER_PID" --arg start "$BRL_LEGACY_UPDATER_START" \
        --argjson request "$request_ids" --argjson global "$global_ids" --arg sha "$slot_sha" --arg source "$source_sha" --arg boot "$boot" \
        --arg workId "$work_id" --arg workMode "$work_mode" --arg inventory "$inventory" '
        {schemaVersion:1,product:"BROray-Light",sourceRelease:"1.0.0-r1",targetRelease:"2.0.0-r1",
         legacyLocks:"owned",legacyPid:$pid,legacyStart:$start,requestIds:$request,globalIds:$global,
         slotManifestSha256:$sha,sourceSlotManifestSha256:$source,legacyBootId:$boot,
         legacyWork:{id:$workId,mode:$workMode,inventory:$inventory},
         engineSha256:"773aaf37893ab100e7023d63c8061d8c4763a4d6186844bb3b671d758c145743"}
        ' > "$staged") || return 1
    ln -T "$staged" "$BRL_R1_JOURNAL" || return 1
    rm "$staged"
}

brl_r1_recorded_lock_safe()
{
    local path ids pid child expected_id field
    path="$1"; ids="$2"; pid="$3"
    [ -e "$path" ] || [ -L "$path" ] || return 0
    brl_r1_directory "$path" || return 1
    [ "$(stat -c '%d:%i' "$path")" = "$(printf '%s' "$ids" | jq -r '.[0]')" ] || return 1
    for child in "$path"/* "$path"/.[!.]* "$path"/..?*; do
        [ -e "$child" ] || [ -L "$child" ] || continue
        case "$child" in "$path/pid") field=1 ;; "$path/operation") field=2 ;; *) return 1 ;; esac
        brl_r1_regular "$child" || return 1
        expected_id="$(printf '%s' "$ids" | jq -r --argjson n "$field" '.[$n]')"
        [ "$(stat -c '%d:%i' "$child")" = "$expected_id" ] || return 1
        case "$field" in
            1) [ "$(cat "$child")" = "$pid" ] || return 1 ;;
            2) [ "$(cat "$child")" = update ] || return 1 ;;
        esac
    done
    # A partial old cleanup is recoverable only inside the recorded directory
    # and with every surviving child matching its exact recorded identity.
}

brl_r1_locks_reconcile_guarded()
{
    local prefix request global pid request_ids global_ids path staged
    brl_r1_receipt_valid || { brl_r1_refuse RECEIPT_INVALID; return 1; }
    prefix="${BRORAY_LIGHT_ROOT_PREFIX:-}"
    request="$prefix/opt/var/lock/broray-light-updater/request.lock"
    global="$prefix/opt/var/lock/broray-light/global-operation.lock"
    pid="$(jq -r '.legacyPid' "$BRL_R1_JOURNAL")"
    request_ids="$(jq -c '.requestIds' "$BRL_R1_JOURNAL")"
    global_ids="$(jq -c '.globalIds' "$BRL_R1_JOURNAL")"
    if [ "$(jq -r '.legacyLocks' "$BRL_R1_JOURNAL")" = cleared ]; then
        [ ! -e "$request" ] && [ ! -L "$request" ] &&
            [ ! -e "$global" ] && [ ! -L "$global" ] || { brl_r1_refuse LEGACY_LOCK_REAPPEARED; return 1; }
        return 0
    fi
    brl_r1_recorded_lock_safe "$request" "$request_ids" "$pid" &&
        brl_r1_recorded_lock_safe "$global" "$global_ids" "$pid" || { brl_r1_refuse LEGACY_LOCK_IDENTITY; return 1; }
    # Validate BOTH before deleting either. Never recursively remove a lock.
    for path in "$global" "$request"; do
        [ -d "$path" ] || continue
        rm -f "$path/pid" "$path/operation" && rmdir "$path" || return 1
    done
    staged="$BRL_R1_JOURNAL.$$.new"
    [ ! -e "$staged" ] && [ ! -L "$staged" ] || return 1
    (umask 077; set -C; jq '.legacyLocks="cleared"' "$BRL_R1_JOURNAL" > "$staged") || return 1
    mv -fT "$staged" "$BRL_R1_JOURNAL"
}

brl_r1_locks_reconcile()
{
    local pid start actual prefix root current path rc
    brl_r1_receipt_valid || { brl_r1_refuse RECEIPT_INVALID; return 1; }
    prefix="${BRORAY_LIGHT_ROOT_PREFIX:-}"; root="$prefix/opt/broray-light"
    for path in "$prefix/opt/broray" "$prefix/opt/etc/init.d/S24broray" \
                "$prefix/opt/var/lock/broray/global-operation.lock"; do
        [ ! -e "$path" ] && [ ! -L "$path" ] || { brl_r1_refuse COOWNERSHIP; return 1; }
    done
    current="$(readlink "$root/current")" || return 1
    case "$current" in releases/1.0.0-r1|releases/2.0.0-r1) ;; *) brl_r1_refuse CURRENT_BINDING; return 1 ;; esac
    brl_r1_directory "$root/$current" && brl_r1_regular "$root/$current/release.json" &&
        jq -e --arg id "${current#releases/}" '.product=="BROray-Light" and .releaseId==$id' \
        "$root/$current/release.json" >/dev/null 2>&1 || { brl_r1_refuse CURRENT_BINDING; return 1; }
    pid="$(jq -r '.legacyPid' "$BRL_R1_JOURNAL")"
    start="$(jq -r '.legacyStart' "$BRL_R1_JOURNAL")"
    actual="$(brl_process_start "$pid" 2>/dev/null || true)"
    [ "$actual" != "$start" ] || { brl_r1_refuse LEGACY_OWNER_STILL_LIVE; return 2; }
    brl_ram_prepare || { brl_r1_refuse RAM_NAMESPACE; return 1; }
    brl_admission_enter || return 1
    rc=0
    brl_r1_locks_reconcile_guarded || rc=$?
    brl_admission_leave || return 1
    return "$rc"
}
