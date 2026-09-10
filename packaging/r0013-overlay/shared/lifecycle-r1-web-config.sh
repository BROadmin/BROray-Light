#!/opt/bin/ash
# Requires lifecycle-r1-platform.sh and its dependencies. Backed-up configuration
# is durable transaction state; operational scratch remains exclusively in RAM.

brl_web_config_paths()
{
    BRL_WEB_CONFIG_ROOT="${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/broray-light/config"
    brl_r1_directory "$BRL_WEB_CONFIG_ROOT" || return 1
    BRL_WEB_CONFIG="$BRL_WEB_CONFIG_ROOT/lighttpd.conf"
    BRL_WEB_OWNER="$BRL_WEB_CONFIG_ROOT/web-publish.json"
}

brl_web_config_original_valid()
{
    local sha
    brl_web_config_paths && brl_r1_regular "$BRL_WEB_CONFIG" && brl_ram_file_valid "$BRL_WEB_OWNER" || return 1
    [ "$(wc -c < "$BRL_WEB_CONFIG")" -le 131072 ] && [ "$(wc -c < "$BRL_WEB_OWNER")" -le 32768 ] || return 1
    sha="$(sha256sum "$BRL_WEB_CONFIG" | awk '{print $1}')"
    jq -e --arg sha "$sha" '.schemaVersion==1 and .owner=="BROray-Light" and .name=="brolight" and
      .policySha256=="e3e0e68b10ef69fce1c504f2689d1ecbd3f8b6b78ee6e7ab03d8ea73d63607dc" and
      .lighttpdConfigSha256==$sha' "$BRL_WEB_OWNER" >/dev/null 2>&1 || return 1
    [ "$(grep -Ec '^[[:space:]]*server\.pid-file[[:space:]]*=' "$BRL_WEB_CONFIG")" = 1 ] &&
        [ "$(grep -Ec '^[[:space:]]*server\.errorlog[[:space:]]*=' "$BRL_WEB_CONFIG")" = 1 ] &&
        grep -Fqx 'server.pid-file = "/opt/broray-light/run/lighttpd.pid"' "$BRL_WEB_CONFIG" &&
        grep -Fqx 'server.errorlog = "/opt/broray-light/logs/lighttpd-error.log"' "$BRL_WEB_CONFIG"
}

brl_web_config_content_sha()
{
    jq -jr --arg key "$1" '.webConfig[$key]' "$BRL_R1_JOURNAL" | sha256sum | awk '{print $1}'
}

brl_web_config_prepare()
{
    local config_mode config_sha owner_sha new_sha
    brl_platform_payload && brl_web_config_paths || return 1
    if ! jq -e '.webConfig' "$BRL_R1_JOURNAL" >/dev/null 2>&1; then
        brl_web_config_original_valid || { brl_r1_refuse WEB_CONFIG_OWNERSHIP; return 1; }
        config_mode="$(stat -c '%a' "$BRL_WEB_CONFIG")"
        case "$config_mode" in 600|644) ;; *) return 1 ;; esac
        config_sha="$(sha256sum "$BRL_WEB_CONFIG" | awk '{print $1}')"
        owner_sha="$(sha256sum "$BRL_WEB_OWNER" | awk '{print $1}')"
        brl_r1_ram_save --rawfile config "$BRL_WEB_CONFIG" --rawfile owner "$BRL_WEB_OWNER" \
            --arg mode "$config_mode" --arg configSha "$config_sha" --arg ownerSha "$owner_sha" '
            .webConfig={schemaVersion:1,phase:"preparing",oldConfig:$config,oldOwner:$owner,
              oldConfigMode:$mode,oldConfigSha:$configSha,oldOwnerSha:$ownerSha,
              newConfig:($config | split("\n") | map(
                if .=="server.pid-file = \"/opt/broray-light/run/lighttpd.pid\"" then
                  "server.pid-file = \"/tmp/broray-light/run/lighttpd.pid\""
                elif .=="server.errorlog = \"/opt/broray-light/logs/lighttpd-error.log\"" then
                  "server.errorlog = \"/tmp/broray-light/logs/lighttpd-error.log\""
                else . end) | join("\n"))}' || return 1
    fi
    if [ "$(jq -r '.webConfig.phase' "$BRL_R1_JOURNAL")" = preparing ]; then
        # No live file has changed yet. Complete the prepared record without
        # adopting a new owner/config after an interrupted receipt write.
        config_sha="$(brl_web_config_content_sha oldConfig)"
        owner_sha="$(brl_web_config_content_sha oldOwner)"
        brl_platform_file "$BRL_WEB_CONFIG" "$config_sha" "$(jq -r '.webConfig.oldConfigMode' "$BRL_R1_JOURNAL")" &&
            brl_platform_file "$BRL_WEB_OWNER" "$owner_sha" 600 || return 1
        new_sha="$(brl_web_config_content_sha newConfig)"
        brl_r1_ram_save --arg sha "$new_sha" '.webConfig.newConfigSha=$sha |
            .webConfig.newOwner=((.webConfig.oldOwner|fromjson|.lighttpdConfigSha256=$sha|tojson)+"\n")' || return 1
        owner_sha="$(brl_web_config_content_sha newOwner)"
        brl_r1_ram_save --arg sha "$owner_sha" '.webConfig.newOwnerSha=$sha | .webConfig.phase="prepared"' || return 1
    fi
    brl_web_config_bound
}

brl_web_config_bound()
{
    local key sha
    brl_platform_payload && brl_web_config_paths || return 1
    jq -e '.webConfig | .schemaVersion==1 and
      (.phase=="prepared" or .phase=="active" or .phase=="restored") and
      (.oldConfigMode=="600" or .oldConfigMode=="644") and
      ([.oldConfig,.newConfig,.oldOwner,.newOwner] | all(type=="string" and length>0 and length<=131072)) and
      ([.oldConfigSha,.newConfigSha,.oldOwnerSha,.newOwnerSha] | all(type=="string" and test("^[0-9a-f]{64}$")))
      ' "$BRL_R1_JOURNAL" >/dev/null 2>&1 || return 1
    for key in oldConfig newConfig oldOwner newOwner; do
        sha="$(jq -r --arg key "${key}Sha" '.webConfig[$key]' "$BRL_R1_JOURNAL")"
        [ "$(brl_web_config_content_sha "$key")" = "$sha" ] || return 1
    done
    jq -e '.webConfig as $w | ($w.oldOwner|fromjson) as $old | ($w.newOwner|fromjson) as $new |
      $old.owner=="BROray-Light" and $old.name=="brolight" and $old.lighttpdConfigSha256==$w.oldConfigSha and
      $new==($old|.lighttpdConfigSha256=$w.newConfigSha)' "$BRL_R1_JOURNAL" >/dev/null 2>&1
}

brl_web_config_targets_valid()
{
    local policy name target suffix old_sha new_sha old_mode staged inode
    policy="$1"
    for name in Config Owner; do
        case "$name" in Config) target="$BRL_WEB_CONFIG"; old_mode="$(jq -r '.webConfig.oldConfigMode' "$BRL_R1_JOURNAL")" ;; Owner) target="$BRL_WEB_OWNER"; old_mode=600 ;; esac
        old_sha="$(jq -r --arg key "old${name}Sha" '.webConfig[$key]' "$BRL_R1_JOURNAL")"
        new_sha="$(jq -r --arg key "new${name}Sha" '.webConfig[$key]' "$BRL_R1_JOURNAL")"
        if [ "$policy" != old ] && brl_platform_file "$target" "$new_sha" 600; then :
        elif [ "$policy" != new ] && brl_platform_file "$target" "$old_sha" "$old_mode"; then :
        else brl_r1_refuse WEB_CONFIG_TARGET_IDENTITY; return 1
        fi
        staged="$BRL_WEB_CONFIG_ROOT/.${target##*/}.r0013-installed"
        if [ -e "$staged" ] || [ -L "$staged" ]; then
            brl_ram_file_valid "$staged" || brl_platform_file "$staged" "$old_sha" "$old_mode" || return 1
            inode="$(stat -c '%d:%i' "$staged")"
            jq -e --arg key "$name" --arg inode "$inode" '.webConfig.staged[$key].inode==$inode' \
                "$BRL_R1_JOURNAL" >/dev/null 2>&1 || { brl_r1_refuse WEB_CONFIG_STAGE_IDENTITY; return 1; }
        fi
    done
}

brl_web_config_write()
{
    local name direction target key sha mode staged inode
    name="$1"; direction="$2"
    case "$direction:$name" in old:Config|old:Owner|new:Config|new:Owner) ;; *) return 1 ;; esac
    case "$name" in Config) target="$BRL_WEB_CONFIG" ;; Owner) target="$BRL_WEB_OWNER" ;; esac
    key="$direction$name"
    sha="$(jq -r --arg key "${key}Sha" '.webConfig[$key]' "$BRL_R1_JOURNAL")"
    mode=600
    if [ "$key" = oldConfig ]; then mode="$(jq -r '.webConfig.oldConfigMode' "$BRL_R1_JOURNAL")"; fi
    staged="$BRL_WEB_CONFIG_ROOT/.${target##*/}.r0013-installed"
    if brl_platform_file "$target" "$sha" "$mode"; then
        if [ -e "$staged" ]; then rm "$staged" && brl_r1_ram_save --arg key "$name" 'del(.webConfig.staged[$key])'; else return 0; fi
        return $?
    fi
    if [ ! -e "$staged" ] && [ ! -L "$staged" ]; then
        (umask 077; set -C; : > "$staged") || return 1
        inode="$(stat -c '%d:%i' "$staged")"
        brl_r1_ram_save --arg key "$name" --arg inode "$inode" '.webConfig.staged[$key]={inode:$inode}' || return 1
    fi
    # All pending candidates were checked before either live file was changed.
    jq -jr --arg key "$key" '.webConfig[$key]' "$BRL_R1_JOURNAL" > "$staged" || return 1
    [ "$(sha256sum "$staged" | awk '{print $1}')" = "$sha" ] || return 1
    chmod "$mode" "$staged" && mv -fT "$staged" "$target" || return 1
    brl_r1_ram_save --arg key "$name" 'del(.webConfig.staged[$key])'
}

brl_web_config_activate()
{
    brl_web_config_prepare && brl_web_config_targets_valid mixed || return 1
    if [ "$(jq -r '.webConfig.phase' "$BRL_R1_JOURNAL")" = active ]; then brl_web_config_targets_valid new; return $?; fi
    [ "$(jq -r '.webConfig.phase' "$BRL_R1_JOURNAL")" = prepared ] || return 1
    brl_web_config_write Config new && brl_web_config_write Owner new &&
        brl_web_config_targets_valid new && brl_r1_ram_save '.webConfig.phase="active"'
}

brl_web_config_restore()
{
    brl_web_config_bound && brl_web_config_targets_valid mixed || return 1
    if [ "$(jq -r '.webConfig.phase' "$BRL_R1_JOURNAL")" = restored ]; then brl_web_config_targets_valid old; return $?; fi
    brl_web_config_write Config old && brl_web_config_write Owner old &&
        brl_web_config_targets_valid old && brl_r1_ram_save '.webConfig.phase="restored"'
}
