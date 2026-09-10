#!/opt/bin/ash
# Requires the r1 admission/journal/RAM helpers. Operates only while the exact
# old updater still owns the live transaction. Boot recovery is a separate gate.

brl_platform_paths()
{
    printf '%s\n' opt/etc/init.d/S24broray-light \
        opt/libexec/broray-light-web-publish/start-gate.sh \
        opt/libexec/broray-light-web-publish/network.sh \
        opt/libexec/broray-light-web-publish/broray-light-web-publish.sh \
        opt/libexec/broray-light-updater/runtime-ram.sh \
        opt/libexec/broray-light-updater/broray-light-updater.sh \
        opt/etc/init.d/S23broray-light-updater
}

brl_platform_file()
{
    [ -f "$1" ] && [ ! -L "$1" ] && [ "$(stat -c '%u:%a' "$1")" = "0:$3" ] &&
        [ "$(sha256sum "$1" | awk '{print $1}')" = "$2" ]
}

brl_platform_payload()
{
    local prefix slot sha path old new count parent
    brl_r1_transition_live || return 1
    prefix="${BRORAY_LIGHT_ROOT_PREFIX:-}"
    slot="$prefix/opt/broray-light/releases/2.0.0-r1"
    brl_r1_directory "$slot" && brl_r1_regular "$slot/APP-SHA256SUMS" || return 1
    sha="$(sha256sum "$slot/APP-SHA256SUMS" | awk '{print $1}')"
    [ "$sha" = "$(jq -r '.slotManifestSha256' "$BRL_R1_JOURNAL")" ] || return 1
    # The exact live legacy transaction already authenticated this manifest.
    # Recheck payload bytes, types and complete app inventory before any write.
    count="$(awk 'END {print NR-1}' "$slot/APP-SHA256SUMS")"
    brl_r1_manifest_valid "$slot" "$count" \
        "$(find "$slot/app" -type f -exec wc -c {} \; | awk '{s+=$1} END {print s+0}')" || return 1
    BRL_PLATFORM_PAYLOAD="$slot/app/share/lifecycle/platform"
    BRL_PLATFORM_MANIFEST="$BRL_PLATFORM_PAYLOAD/manifest.json"
    brl_r1_directory "$BRL_PLATFORM_PAYLOAD" && brl_r1_regular "$BRL_PLATFORM_MANIFEST" || return 1
    jq -e '.schemaVersion==1 and .product=="BROray-Light" and .sourceRelease=="1.0.0-r1" and
      .targetRelease=="2.0.0-r1" and (.files|type=="array" and length==7 and all(
        .mode==493 and (.newSha256|type=="string" and test("^[0-9a-f]{64}$")) and
        (.oldSha256==null or (.oldSha256|type=="string" and test("^[0-9a-f]{64}$")))))
      ' "$BRL_PLATFORM_MANIFEST" >/dev/null 2>&1 || return 1
    [ "$(jq -r '.files[].path' "$BRL_PLATFORM_MANIFEST")" = "$(brl_platform_paths)" ] || return 1
    for path in $(brl_platform_paths); do
        old="$(jq -r --arg path "$path" '.files[]|select(.path==$path)|.oldSha256' "$BRL_PLATFORM_MANIFEST")"
        new="$(jq -r --arg path "$path" '.files[]|select(.path==$path)|.newSha256' "$BRL_PLATFORM_MANIFEST")"
        brl_platform_file "$BRL_PLATFORM_PAYLOAD/new/$path" "$new" 644 || return 1
        case "$path:$old" in
            opt/libexec/broray-light-updater/runtime-ram.sh:null) ;;
            *:null) return 1 ;;
            *) brl_platform_file "$BRL_PLATFORM_PAYLOAD/r1/$path" "$old" 644 || return 1 ;;
        esac
        # No symlink ancestor below the explicitly rooted /opt platform.
        parent="${path%/*}"
        while :; do
            brl_r1_directory "$prefix/$parent" || return 1
            [ "$parent" != opt ] || break
            parent="${parent%/*}"
        done
    done
    BRL_PLATFORM_SHA="$(sha256sum "$BRL_PLATFORM_MANIFEST" | awk '{print $1}')"
}

brl_platform_targets_valid()
{
    local path old new target policy
    policy="$1"
    for path in $(brl_platform_paths); do
        target="${BRORAY_LIGHT_ROOT_PREFIX:-}/$path"
        old="$(jq -r --arg path "$path" '.files[]|select(.path==$path)|.oldSha256' "$BRL_PLATFORM_MANIFEST")"
        new="$(jq -r --arg path "$path" '.files[]|select(.path==$path)|.newSha256' "$BRL_PLATFORM_MANIFEST")"
        if [ "$policy" != old ] && brl_platform_file "$target" "$new" 755; then continue; fi
        if [ "$policy" != new ]; then
            if [ "$old" = null ]; then [ ! -e "$target" ] && [ ! -L "$target" ] && continue
            elif brl_platform_file "$target" "$old" 755; then continue
            fi
        fi
        brl_r1_refuse PLATFORM_TARGET_IDENTITY; return 1
    done
}

brl_platform_replace()
{
    local path direction sha target staged inode existing_matches
    path="$1"; direction="$2"
    target="${BRORAY_LIGHT_ROOT_PREFIX:-}/$path"
    sha="$(jq -r --arg path "$path" --arg direction "$direction" \
        '.files[]|select(.path==$path)|if $direction=="new" then .newSha256 else .oldSha256 end' "$BRL_PLATFORM_MANIFEST")"
    staged="${target%/*}/.${target##*/}.r0013-installed"
    if [ "$sha" = null ]; then
        if [ -e "$staged" ] || [ -L "$staged" ]; then
            [ -f "$staged" ] && [ ! -L "$staged" ] || return 1
            case "$(stat -c '%u:%a' "$staged")" in 0:600|0:755) ;; *) return 1 ;; esac
            inode="$(stat -c '%d:%i' "$staged")"
            jq -e --arg path "$path" --arg inode "$inode" '.platform.staged[$path].inode==$inode' \
                "$BRL_R1_JOURNAL" >/dev/null 2>&1 || return 1
            rm "$staged" && brl_r1_ram_save --arg path "$path" 'del(.platform.staged[$path])' || return 1
        fi
        [ ! -e "$target" ] && [ ! -L "$target" ] && return 0
        # Targets were checked globally before any mutation and rechecked here.
        brl_platform_file "$target" "$(jq -r --arg path "$path" '.files[]|select(.path==$path)|.newSha256' "$BRL_PLATFORM_MANIFEST")" 755 && rm "$target"
        return $?
    fi
    existing_matches=false
    brl_platform_file "$target" "$sha" 755 && existing_matches=true
    if [ -e "$staged" ] || [ -L "$staged" ]; then
        [ -f "$staged" ] && [ ! -L "$staged" ] || return 1
        case "$(stat -c '%u:%a' "$staged")" in 0:600|0:755) ;; *) return 1 ;; esac
        inode="$(stat -c '%d:%i' "$staged")"
        jq -e --arg path "$path" --arg inode "$inode" \
            '.platform.staged[$path].inode==$inode' \
            "$BRL_R1_JOURNAL" >/dev/null 2>&1 || return 1
        if [ "$existing_matches" = true ]; then
            rm "$staged" && brl_r1_ram_save --arg path "$path" 'del(.platform.staged[$path])'; return $?
        fi
    else
        [ "$existing_matches" != true ] || return 0
        (umask 077; set -C; : > "$staged") || return 1
        inode="$(stat -c '%d:%i' "$staged")"
    fi
    brl_r1_ram_save --arg path "$path" --arg inode "$inode" --arg sha "$sha" \
        '.platform.staged[$path]={inode:$inode,sha256:$sha}' || return 1
    # This inode is a recorded installed candidate adjacent to its final path,
    # not a download/extraction scratch file. Rewrite only that owned candidate.
    cat "$BRL_PLATFORM_PAYLOAD/$direction/$path" > "$staged" && chmod 755 "$staged" &&
        brl_platform_file "$staged" "$sha" 755 || return 1
    [ "$(stat -c '%d' "$staged")" = "$(stat -c '%d' "${target%/*}")" ] || return 1
    mv -fT "$staged" "$target" || return 1
    brl_r1_ram_save --arg path "$path" 'del(.platform.staged[$path])'
}

brl_platform_activate()
{
    local path
    brl_platform_payload || { brl_r1_refuse PLATFORM_PAYLOAD; return 1; }
    if jq -e '.platform' "$BRL_R1_JOURNAL" >/dev/null 2>&1; then
        jq -e --arg sha "$BRL_PLATFORM_SHA" '.platform.manifestSha256==$sha and
            (.platform.phase=="prepared" or .platform.phase=="installed")' "$BRL_R1_JOURNAL" >/dev/null 2>&1 || return 1
        if [ "$(jq -r '.platform.phase' "$BRL_R1_JOURNAL")" = installed ]; then
            brl_platform_targets_valid new; return $?
        fi
        brl_platform_targets_valid mixed || return 1
    else
        brl_platform_targets_valid old || return 1
        brl_r1_ram_save --arg sha "$BRL_PLATFORM_SHA" '.platform={phase:"prepared",manifestSha256:$sha}' || return 1
    fi
    for path in $(brl_platform_paths); do brl_platform_replace "$path" new || return 1; done
    brl_platform_targets_valid new || return 1
    brl_r1_ram_save '.platform.phase="installed"'
}

brl_platform_restore()
{
    local path paths
    brl_platform_payload || { brl_r1_refuse PLATFORM_PAYLOAD; return 1; }
    jq -e --arg sha "$BRL_PLATFORM_SHA" '.platform.manifestSha256==$sha and
        (.platform.phase=="prepared" or .platform.phase=="installed" or .platform.phase=="restored")' \
        "$BRL_R1_JOURNAL" >/dev/null 2>&1 || return 1
    if [ "$(jq -r '.platform.phase' "$BRL_R1_JOURNAL")" = restored ]; then
        brl_platform_targets_valid old; return $?
    fi
    brl_platform_targets_valid mixed || return 1
    paths="$(brl_platform_paths | awk '{a[NR]=$0} END {for(i=NR;i>0;i--)print a[i]}')"
    for path in $paths; do brl_platform_replace "$path" r1 || return 1; done
    brl_platform_targets_valid old && brl_r1_ram_save '.platform.phase="restored"'
}
