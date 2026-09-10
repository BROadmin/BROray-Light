#!/opt/bin/ash
# Requires r1 platform/RAM helpers and the signed slot's service-process and
# xray-process definitions. Durable journal stores identities, not RAM payload.

brl_legacy_tree_names()
{
    printf '%s\n' run logs tmp update
}

brl_legacy_quiesce()
{
    local ROOT BRL_RAM role pid pids start i path actual binary
    brl_r1_transition_authorized || return 1
    ROOT="${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/broray-light"
    BRL_RAM="$ROOT" # Only this scoped function addresses the OLD PID locations.
    for role in daemon web auth; do
        brl_service_role "$role" || return 1
        pid=''
        if [ -e "$BRL_ROLE_PID" ] || [ -L "$BRL_ROLE_PID" ]; then
            brl_r1_regular "$BRL_ROLE_PID" && [ "$(stat -c '%h' "$BRL_ROLE_PID")" = 1 ] || return 1
            case "$(stat -c '%a' "$BRL_ROLE_PID")" in 600|644) ;; *) return 1 ;; esac
            pid="$(awk 'NR==1 && /^[0-9]+$/ && $0>1 {p=$0;next} {bad=1} END{if(NR==1&&!bad)print p;else exit 1}' "$BRL_ROLE_PID")" || return 1
            if [ -n "$(brl_service_start_id "$pid")" ]; then
                brl_service_identity "$role" "$pid" >/dev/null || { brl_r1_refuse LEGACY_FOREIGN_PID; return 1; }
            else pid=''
            fi
        fi
        pids="$(brl_service_pids "$role")"
        [ "$pids" = "$pid" ] || { brl_r1_refuse LEGACY_UNRECORDED_PROCESS; return 1; }
        if [ -n "$pid" ]; then
            start="$(brl_service_identity "$role" "$pid")" || return 1
            [ "$start" = "$(brl_service_identity "$role" "$pid")" ] || return 1
            case "$role" in auth) kill -QUIT "$pid" ;; *) kill -TERM "$pid" ;; esac || return 1
            i=0
            while [ "$(brl_service_start_id "$pid")" = "$start" ] && [ "$i" -lt 10 ]; do sleep 1; i=$((i+1)); done
            [ "$(brl_service_start_id "$pid")" != "$start" ] || return 1
        fi
        [ -z "$(brl_service_pids "$role")" ] || return 1
    done
    binary="$ROOT/run/web-new/native-auth/broray-ndm-auth-nginx"
    for path in /proc/[0-9]*/exe; do
        actual="$(readlink "$path" 2>/dev/null || true)"
        case "$actual" in "$binary"|"$binary (deleted)") brl_r1_refuse LEGACY_AUTH_WORKER_LIVE; return 1 ;; esac
    done
    BRORAY_XRAY_BINARY="$ROOT/runtime/xray"; BRORAY_XRAY_CONFIG="$ROOT/config/config.json"
    if [ -n "$(broray_xray_runtime_pids 2>/dev/null || true)" ]; then
        broray_xray_runtime_signal TERM || return 1
        i=0
        while [ -n "$(broray_xray_runtime_pids 2>/dev/null || true)" ] && [ "$i" -lt 10 ]; do sleep 1; i=$((i+1)); done
    fi
    [ -z "$(broray_xray_runtime_pids 2>/dev/null || true)" ] || return 1
    # Do not move files beneath a surviving old CLI/CGI. The current migration
    # and its ancestors are the only product scripts allowed at this boundary.
    for path in /proc/[0-9]*/cmdline; do
        pid="${path#/proc/}"; pid="${pid%/cmdline}"
        [ -n "$(brl_service_start_id "$pid")" ] || continue
        if tr '\000' '\n' < "$path" 2>/dev/null | awk -v root="$ROOT/" '
          NR<=3 && index($0,root)==1 && ($0~/\/bin\// || $0~/\/web-new\//) {found=1}
          END{exit !found}'; then
            brl_r1_owner_ancestor "$pid" || { brl_r1_refuse LEGACY_APPLICATION_WORKER_LIVE; return 1; }
        fi
    done
}

brl_tree_inventory()
{
    local root identities
    root="$1"; identities="$2"
    brl_r1_directory "$root" || return 1
    find "$root" -print | LC_ALL=C sort | while IFS= read -r path; do
        relative="${path#"$root"}"; relative="${relative#/}"; [ -n "$relative" ] || relative=.
        case "$relative" in *[!A-Za-z0-9_./-]*|*../*|../*|*/..|..) return 1 ;; esac
        [ ! -L "$path" ] && [ "$(stat -c '%u' "$path")" = 0 ] || return 1
        mode="$(stat -c '%a' "$path")"; inode=-
        [ "$identities" != yes ] || inode="$(stat -c '%d:%i' "$path")"
        if [ -d "$path" ]; then
            case "$mode" in 700|755) ;; *) return 1 ;; esac
            printf 'D %s %s 0 - %s\n' "$mode" "$inode" "$relative"
        elif [ -f "$path" ]; then
            case "$mode" in 600|644|700|755) ;; *) return 1 ;; esac
            [ "$(stat -c '%h' "$path")" = 1 ] || return 1
            printf 'F %s %s %s %s %s\n' "$mode" "$inode" "$(wc -c < "$path")" "$(sha256sum "$path" | awk '{print $1}')" "$relative"
        else return 1
        fi
    done
}

brl_tree_context()
{
    brl_platform_payload && brl_r1_ram_bound && brl_ram_prepare || return 1
    BRL_TREE_ROOT="${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/broray-light"
    BRL_TREE_BACKUP="$BRL_TRANSITION_PRIVATE/runtime-r1"
    brl_ram_child "$BRL_TREE_BACKUP"
}

brl_tree_content()
{
    jq -r --arg name "$1" '.runtimeTrees[$name].contentInventory' "$BRL_R1_JOURNAL"
}

brl_tree_survivors_valid()
{
    local name source current expected row
    name="$1"; source="$BRL_TREE_ROOT/$name"
    [ -e "$source" ] || [ -L "$source" ] || return 0
    [ ! -L "$source" ] || { [ "$(readlink "$source")" = "$BRL_RAM/$name" ]; return $?; }
    current="$(brl_tree_inventory "$source" yes)" || return 1
    expected="$(jq -r --arg name "$name" '.runtimeTrees[$name].inventory' "$BRL_R1_JOURNAL")"
    printf '%s\n' "$current" | while IFS= read -r row; do
        printf '%s\n' "$expected" | grep -Fqx "$row" || return 1
    done
}

brl_tree_prepare_all()
{
    local name source inventory content private backup inode mode
    brl_tree_context && brl_legacy_quiesce || return 1
    for name in $(brl_legacy_tree_names); do
        source="$BRL_TREE_ROOT/$name"
        if ! jq -e --arg name "$name" '.runtimeTrees[$name]' "$BRL_R1_JOURNAL" >/dev/null 2>&1; then
            if [ ! -e "$source" ] && [ ! -L "$source" ]; then inventory=''; content=''
            else
                inventory="$(brl_tree_inventory "$source" yes)" && content="$(brl_tree_inventory "$source" no)" || { brl_r1_refuse LEGACY_TREE_IDENTITY; return 1; }
                printf '%s\n' "$inventory" | awk 'NF!=6 {bad=1} {bytes+=$4} END{exit (bad || NR>2048 || bytes>67108864)}' || return 1
                if [ "$name" = run ]; then
                    for private in web-new web-new/sessions web-new/native-auth locks; do
                        [ ! -e "$source/$private" ] || brl_ram_dir_valid "$source/$private" || return 1
                    done
                    [ ! -d "$source/locks" ] || [ -z "$(find "$source/locks" -mindepth 1 -print)" ] || return 1
                fi
            fi
            brl_r1_ram_save --arg name "$name" --arg inventory "$inventory" --arg content "$content" \
                '.runtimeTrees[$name]={phase:"planned",inventory:$inventory,contentInventory:$content}' || return 1
        fi
        brl_tree_survivors_valid "$name" || return 1
    done
    # No old file is removed until ALL roots have been admitted and copied.
    for name in $(brl_legacy_tree_names); do
        content="$(brl_tree_content "$name")"
        [ -n "$content" ] || continue
        backup="$BRL_TREE_BACKUP/$name"
        if [ ! -e "$backup" ] && [ ! -L "$backup" ]; then
            (umask 077; mkdir "$backup") || return 1
            inode="$(stat -c '%d:%i' "$backup")"
            brl_r1_ram_save --arg name "$name" --arg inode "$inode" '.runtimeTrees[$name].backupId=$inode' || return 1
        fi
        brl_r1_directory "$backup" &&
            [ "$(stat -c '%d:%i' "$backup")" = "$(jq -r --arg name "$name" '.runtimeTrees[$name].backupId' "$BRL_R1_JOURNAL")" ] || return 1
        [ "$(brl_tree_inventory "$backup" no)" != "$content" ] || continue
        # Resume a partial RAM backup only while the full original source is
        # still present, and only inside the previously recorded backup inode.
        [ "$(brl_tree_inventory "$BRL_TREE_ROOT/$name" yes)" = "$(jq -r --arg name "$name" '.runtimeTrees[$name].inventory' "$BRL_R1_JOURNAL")" ] || return 1
        brl_tree_copy_shape "$name" "$backup" old || return 1
        brl_tree_copy_children "$BRL_TREE_ROOT/$name" "$backup" || return 1
        mode="$(printf '%s\n' "$content" | awk '$6=="." {print $2}')"
        chmod "$mode" "$backup" && [ "$(brl_tree_inventory "$backup" no)" = "$content" ] || return 1
    done
}

brl_tree_remove_source()
{
    local name source row type mode inode size sha relative path expected actual
    name="$1"; source="$BRL_TREE_ROOT/$name"
    brl_tree_survivors_valid "$name" || return 1
    if [ -L "$source" ]; then return 0; fi
    [ -e "$source" ] || return 0
    expected="$(jq -r --arg name "$name" '.runtimeTrees[$name].inventory' "$BRL_R1_JOURNAL")"
    # Reverse path order, not line/type order: children always precede parent.
    printf '%s\n' "$expected" | sort -k6,6r | while read -r type mode inode size sha relative; do
        path="$source"; [ "$relative" = . ] || path="$source/$relative"
        [ -e "$path" ] || [ -L "$path" ] || continue
        [ ! -L "$path" ] && [ "$(stat -c '%u:%a:%d:%i' "$path")" = "0:$mode:$inode" ] || return 1
        case "$type" in
            F) [ -f "$path" ] && [ "$(stat -c '%h' "$path")" = 1 ] &&
                [ "$(sha256sum "$path" | awk '{print $1}')" = "$sha" ] && rm "$path" || return 1 ;;
            D) rmdir "$path" || return 1 ;;
            *) return 1 ;;
        esac
    done
}

brl_tree_promote()
{
    local name source destination phase content
    brl_tree_prepare_all || return 1
    for name in $(brl_legacy_tree_names); do
        source="$BRL_TREE_ROOT/$name"; destination="$BRL_RAM/$name"
        brl_ram_child "$destination" || return 1
        phase="$(jq -r --arg name "$name" '.runtimeTrees[$name].phase' "$BRL_R1_JOURNAL")"
        case "$phase" in planned|copied|active) ;; *) return 1 ;; esac
        if [ "$phase" = active ]; then
            [ -L "$source" ] && [ "$(readlink "$source")" = "$destination" ] || return 1
            continue
        fi
        content="$(brl_tree_content "$name")"
        if [ "$phase" = planned ]; then
            # The protected destination must still be empty except the RAM
            # primitive's known empty run skeleton. Copying old state over a
            # running new service is never allowed.
            if ! jq -e --arg name "$name" '.runtimeTrees[$name].ramDestinationId' "$BRL_R1_JOURNAL" >/dev/null; then
                if [ "$name" = run ]; then
                    [ -z "$(find "$destination" -type f -o -type l)" ] || return 1
                    [ -z "$(find "$destination/locks" -mindepth 1 -print)" ] || return 1
                else [ -z "$(find "$destination" -mindepth 1 -print)" ] || return 1
                fi
                brl_r1_ram_save --arg name "$name" --arg inode "$(stat -c '%d:%i' "$destination")" \
                    '.runtimeTrees[$name].ramDestinationId=$inode' || return 1
            fi
            [ "$(stat -c '%d:%i' "$destination")" = "$(jq -r --arg name "$name" '.runtimeTrees[$name].ramDestinationId' "$BRL_R1_JOURNAL")" ] || return 1
            brl_tree_copy_shape "$name" "$destination" ram || return 1
            if [ -n "$content" ]; then brl_tree_copy_children "$BRL_TREE_BACKUP/$name" "$destination" || return 1; fi
            brl_tree_copy_complete "$name" "$destination" ram || return 1
            brl_r1_ram_save --arg name "$name" '.runtimeTrees[$name].phase="copied"' || return 1
        fi
        brl_tree_copy_complete "$name" "$destination" ram || return 1
        brl_tree_remove_source "$name" || return 1
        if [ ! -e "$source" ] && [ ! -L "$source" ]; then ln -s "$destination" "$source" || return 1; fi
        [ -L "$source" ] && [ "$(readlink "$source")" = "$destination" ] || return 1
        brl_r1_ram_save --arg name "$name" '.runtimeTrees[$name].phase="active"' || return 1
    done
}

brl_tree_copy_children()
{
    local source destination child
    source="$1"; destination="$2"
    for child in "$source"/* "$source"/.[!.]* "$source"/..?*; do
        [ -e "$child" ] || [ -L "$child" ] || continue
        cp -a "$child" "$destination/" || return 1
    done
}

brl_tree_copy_shape()
{
    local name tree policy content rows
    name="$1"; tree="$2"; policy="$3"
    content="$(brl_tree_content "$name")"
    rows="$(brl_tree_inventory "$tree" no)" || return 1
    # Known partial copies can be resumed only inside the recorded root inode.
    # Reject unexpected children or object types before cp can overwrite data.
    printf '%s\n' "$rows" | while read -r type mode inode size sha relative; do
        if [ "$policy:$name" = ram:run ]; then
            case "$type:$relative" in D:locks|D:web-new|D:web-new/sessions) continue ;; esac
        fi
        [ "$type:$relative" != D:. ] || continue
        printf '%s\n' "$content" | awk -v type="$type" -v relative="$relative" \
            '$1==type && $6==relative {found++} END{exit found!=1}' || return 1
    done
}

brl_tree_copy_complete()
{
    local name tree policy content
    name="$1"; tree="$2"; policy="$3"
    brl_tree_copy_shape "$name" "$tree" "$policy" || return 1
    content="$(brl_tree_content "$name")"
    [ -n "$content" ] || return 0
    printf '%s\n' "$content" | while read -r type mode inode size sha relative; do
        path="$tree"; [ "$relative" = . ] || path="$tree/$relative"
        [ ! -L "$path" ] && [ "$(stat -c '%u' "$path")" = 0 ] || return 1
        if [ "$relative" = . ] && [ "$policy" = ram ]; then expected=700; else expected="$mode"; fi
        [ "$(stat -c '%a' "$path")" = "$expected" ] || return 1
        case "$type" in
            D) [ -d "$path" ] || return 1 ;;
            F) [ -f "$path" ] && [ "$(stat -c '%h' "$path")" = 1 ] &&
                [ "$(wc -c < "$path")" = "$size" ] && [ "$(sha256sum "$path" | awk '{print $1}')" = "$sha" ] || return 1 ;;
            *) return 1 ;;
        esac
    done
}

brl_tree_restore()
{
    local name source staged content phase inode
    brl_tree_context || return 1
    # The coordinated rollback driver must stop the new service before calling
    # this function. Here aliases still allow the same exact process checks.
    brl_legacy_quiesce || return 1
    for name in $(brl_legacy_tree_names); do
        source="$BRL_TREE_ROOT/$name"; staged="$BRL_TREE_ROOT/.$name.r0013-restored"
        phase="$(jq -r --arg name "$name" '.runtimeTrees[$name].phase' "$BRL_R1_JOURNAL")"
        case "$phase" in planned|copied|active|restoring|restored) ;; *) return 1 ;; esac
        content="$(brl_tree_content "$name")"
        if [ "$phase" = restoring ] && [ ! -L "$source" ] && [ -d "$source" ] &&
            [ ! -e "$staged" ] && [ ! -L "$staged" ] && [ -n "$content" ] &&
            brl_tree_copy_complete "$name" "$source" old; then
            brl_r1_ram_save --arg name "$name" '.runtimeTrees[$name].phase="restored"' || return 1
            continue
        fi
        if [ "$phase" = restored ]; then
            if [ -n "$content" ]; then brl_tree_copy_complete "$name" "$source" old || return 1
            else [ ! -e "$source" ] && [ ! -L "$source" ] || return 1
            fi
            continue
        fi
        if [ -n "$content" ]; then
            [ "$(brl_tree_inventory "$BRL_TREE_BACKUP/$name" no)" = "$content" ] || return 1
            if [ ! -e "$staged" ] && [ ! -L "$staged" ]; then
                (umask 077; mkdir "$staged") || return 1
                inode="$(stat -c '%d:%i' "$staged")"
                brl_r1_ram_save --arg name "$name" --arg inode "$inode" '.runtimeTrees[$name].restoreId=$inode' || return 1
            fi
            brl_r1_directory "$staged" &&
                [ "$(stat -c '%d:%i' "$staged")" = "$(jq -r --arg name "$name" '.runtimeTrees[$name].restoreId' "$BRL_R1_JOURNAL")" ] || return 1
            brl_tree_copy_shape "$name" "$staged" old || return 1
            cp -a "$BRL_TREE_BACKUP/$name/." "$staged/" && brl_tree_copy_complete "$name" "$staged" old || return 1
        fi
        brl_r1_ram_save --arg name "$name" '.runtimeTrees[$name].phase="restoring"' || return 1
        if [ -L "$source" ]; then
            [ "$(readlink "$source")" = "$BRL_RAM/$name" ] && rm "$source" || return 1
        elif [ -e "$source" ]; then
            # A partial promotion still has only original, recorded survivors.
            brl_tree_remove_source "$name" || return 1
        fi
        if [ -n "$content" ]; then mv -T "$staged" "$source" && brl_tree_copy_complete "$name" "$source" old || return 1; fi
        brl_r1_ram_save --arg name "$name" '.runtimeTrees[$name].phase="restored"' || return 1
    done
}
