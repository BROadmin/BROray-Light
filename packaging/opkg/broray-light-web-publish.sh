#!/opt/bin/ash

# Ownership-safe BROray-Light publication through KeenDNS HTTP Proxy.
# Derived from the verified updater-era r23 web-publish safety contract, but
# scoped to one package-owned Light object and no full-BROray namespaces.

ROOT_PREFIX="${BRORAY_LIGHT_ROOT_PREFIX:-}"
APP_ROOT="${BRORAY_LIGHT_WEB_ROOT:-$ROOT_PREFIX/opt/broray-light}"
LIFECYCLE_ROOT="${BRORAY_LIGHT_WEB_LIFECYCLE_ROOT:-$ROOT_PREFIX/opt/libexec/broray-light-web-publish}"
NDMC="${BRORAY_LIGHT_WEB_NDMC:-ndmc}"
NAME='brolight'
PORT=8080
OWNER="$APP_ROOT/config/web-publish.json"
RECOVERY="$APP_ROOT/config/web-publish-recovery-required.json"
LIGHTTPD_CONFIG="$APP_ROOT/config/lighttpd.conf"
POLICY="$LIFECYCLE_ROOT/policy.sh"
NETWORK="$LIFECYCLE_ROOT/network.sh"
BASELINE_CONFIG_SHA256='816aed2ab8fe59092d31a1cb1f80fe714cc31f8fe6ece45e5dfde09888bcc661'
VERIFY_ATTEMPTS="${BRORAY_LIGHT_WEB_VERIFY_ATTEMPTS:-8}"
VERIFY_DELAY="${BRORAY_LIGHT_WEB_VERIFY_DELAY_SECONDS:-1}"

web_error()
{
    printf 'BRORAY_LIGHT_WEB_PUBLISH_ERROR:%s:%s:%s\n' "$1" "$2" "$3" >&2
}

[ -r "$POLICY" ] && [ ! -L "$POLICY" ] || {
    web_error library WRITE_POLICY_UNAVAILABLE 'Package-owned write policy unavailable.'
    exit 1
}
[ -r "$NETWORK" ] && [ ! -L "$NETWORK" ] || {
    web_error library NETWORK_LIBRARY_UNAVAILABLE 'Package-owned LAN detector unavailable.'
    exit 1
}
. "$POLICY" || exit 1
. "$NETWORK" || exit 1

policy_require()
{
    broray_light_web_policy_require web-publish || {
        web_error "$1" WRITE_POLICY_INVALID 'Web publication write policy is disabled or invalid.'
        return 1
    }
}

sha256_file()
{
    [ -f "$1" ] && [ ! -L "$1" ] || return 1
    sha256sum "$1" | awk 'NR==1{print $1}'
}

ipv4_valid()
{
    broray_light_web_ipv4_valid "${1:-}"
}

serialization_valid()
{
    case "${1:-}" in present|omitted) return 0 ;; *) return 1 ;; esac
}

command_read_allowed()
{
    case "${1:-}" in 'show running-config'|'show ndns') return 0 ;; *) return 1 ;; esac
}

command_write_allowed()
{
    command_text="${1:-}"
    case "$command_text" in
        'system configuration save'|"ip http proxy $NAME"|"ip http proxy $NAME domain ndns"|"ip http proxy $NAME ssl redirect"|"ip http proxy $NAME security-level public"|"no ip http proxy $NAME") return 0 ;;
    esac
    set -- $command_text
    [ "$#" -eq 8 ] &&
    [ "$1" = ip ] && [ "$2" = http ] && [ "$3" = proxy ] &&
    [ "$4" = "$NAME" ] && [ "$5" = upstream ] && [ "$6" = http ] &&
    ipv4_valid "$7" && [ "$8" = "$PORT" ] &&
    [ "$command_text" = "ip http proxy $NAME upstream http $7 $8" ]
}

run_ndmc()
{
    command_text="${1:-}"
    if command_read_allowed "$command_text"; then
        :
    elif command_write_allowed "$command_text"; then
        policy_require dispatch || return 1
    else
        web_error dispatch COMMAND_NOT_AUTHORIZED 'Command is outside the closed Light HTTP Proxy grammar.'
        return 126
    fi
    "$NDMC" -c "$command_text"
}

running_config()
{
    target="$1"
    run_ndmc 'show running-config' >"$target" 2>"$target.err" || {
        rm -f "$target" "$target.err"
        return 1
    }
    rm -f "$target.err"
}

ndns_identity()
{
    target="$APP_ROOT/tmp/web-publish-ndns.$$.out"
    run_ndmc 'show ndns' >"$target" 2>"$target.err" || {
        rm -f "$target" "$target.err"
        return 1
    }
    ndns_name="$(sed -n 's/^[[:space:]]*name:[[:space:]]*//p' "$target" | sed -n '1p')"
    ndns_domain="$(sed -n 's/^[[:space:]]*domain:[[:space:]]*//p' "$target" | sed -n '1p')"
    ndns_access="$(sed -n 's/^[[:space:]]*access:[[:space:]]*//p' "$target" | sed -n '1p')"
    ndns_updated="$(sed -n 's/^[[:space:]]*updated:[[:space:]]*//p' "$target" | sed -n '1p')"
    rm -f "$target" "$target.err"
    case "$ndns_name" in ''|*[!A-Za-z0-9-]*) return 1 ;; esac
    case "$ndns_domain" in ''|*[!A-Za-z0-9.-]*|.*|*.) return 1 ;; esac
    [ "$ndns_access" = cloud ] && [ "$ndns_updated" = yes ] || return 1
    printf '%s.%s\n' "$ndns_name" "$ndns_domain"
}

proxy_block()
{
    awk -v wanted="ip http proxy $NAME" '
      {
        line=$0; sub(/^[[:space:]]*/,"",line); sub(/[[:space:]]*$/,"",line)
      }
      line==wanted {inside=1}
      inside {print line}
      inside && line=="!" {exit}
    ' "$1"
}

proxy_exists()
{
    proxy_block "$1" | grep -Fx "ip http proxy $NAME" >/dev/null 2>&1
}

proxy_profile()
{
    config="$1"
    host="$2"
    block="$(proxy_block "$config")" || return 1
    [ -n "$block" ] || return 1
    parents="$(awk -v wanted="ip http proxy $NAME" '
      {line=$0; sub(/^[[:space:]]*/,"",line); sub(/[[:space:]]*$/,"",line); if(line==wanted)n++}
      END{print n+0}' "$config")"
    [ "$parents" = 1 ] || return 1
    [ "$(printf '%s\n' "$block" | grep -Fxc '!')" = 1 ] || return 1
    [ "$(printf '%s\n' "$block" | tail -n 1)" = '!' ] || return 1
    [ "$(printf '%s\n' "$block" | grep -Fxc "ip http proxy $NAME")" = 1 ] || return 1
    [ "$(printf '%s\n' "$block" | grep -Fxc "upstream http $host $PORT")" = 1 ] || return 1
    domain_count="$(printf '%s\n' "$block" | grep -Fxc 'domain ndns' || true)"
    ssl_count="$(printf '%s\n' "$block" | grep -Fxc 'ssl redirect' || true)"
    security_count="$(printf '%s\n' "$block" | grep -Fxc 'security-level public' || true)"
    [ "$domain_count" -le 1 ] && [ "$ssl_count" -le 1 ] && [ "$security_count" -le 1 ] || return 1
    [ "$domain_count" -eq 1 ] && domain_state=present || domain_state=omitted
    [ "$ssl_count" -eq 1 ] && ssl_state=present || ssl_state=omitted
    [ "$security_count" -eq 1 ] && security_state=present || security_state=omitted
    expected_count=$((2 + domain_count + ssl_count + security_count))
    actual_count="$(printf '%s\n' "$block" | awk 'NF && $0!="!"{n++} END{print n+0}')"
    [ "$actual_count" = "$expected_count" ] || return 1
    printf '%s\t%s\t%s\n' "$domain_state" "$ssl_state" "$security_state"
}

proxy_exact()
{
    profile="$(proxy_profile "$1" "$2")" || return 1
    if [ "$#" -eq 5 ]; then
        [ "$profile" = "$3	$4	$5" ] || return 1
    fi
}

config_bind()
{
    [ -f "$LIGHTTPD_CONFIG" ] && [ ! -L "$LIGHTTPD_CONFIG" ] || return 1
    [ "$(grep -c '^server\.bind = "[0-9.]*"$' "$LIGHTTPD_CONFIG" 2>/dev/null)" = 1 ] || return 1
    sed -n 's/^server\.bind = "\([0-9.]*\)"$/\1/p' "$LIGHTTPD_CONFIG"
}

config_owned_exact()
{
    host="$1"
    expected_sha="$2"
    [ "$(config_bind)" = "$host" ] && [ "$(sha256_file "$LIGHTTPD_CONFIG")" = "$expected_sha" ]
}

config_prepare_initial()
{
    [ "$(sha256_file "$LIGHTTPD_CONFIG")" = "$BASELINE_CONFIG_SHA256" ] &&
    [ "$(config_bind)" = 127.0.0.1 ]
}

config_set_bind()
{
    host="$1"
    current="$2"
    [ "$(config_bind)" = "$current" ] || return 1
    temporary="$LIGHTTPD_CONFIG.new.$$"
    sed "s/^server\.bind = \"$current\"$/server.bind = \"$host\"/" \
        "$LIGHTTPD_CONFIG" >"$temporary" || { rm -f "$temporary"; return 1; }
    [ "$(grep -c "^server\\.bind = \"$host\"$" "$temporary")" = 1 ] || {
        rm -f "$temporary"; return 1
    }
    chmod 600 "$temporary" 2>/dev/null || true
    if [ -n "${BRORAY_LIGHT_WEB_CONFIG_TEST_COMMAND:-}" ]; then
        "$BRORAY_LIGHT_WEB_CONFIG_TEST_COMMAND" "$temporary" || { rm -f "$temporary"; return 1; }
    else
        lighttpd -tt -f "$temporary" >/dev/null 2>&1 || { rm -f "$temporary"; return 1; }
    fi
    mv -f "$temporary" "$LIGHTTPD_CONFIG"
}

owner_valid()
{
    [ -f "$OWNER" ] && [ ! -L "$OWNER" ] || return 1
    policy_sha="$(broray_light_web_policy_sha256)" || return 1
    jq -e --arg name "$NAME" --arg policySha "$policy_sha" '
      .schemaVersion==1 and .owner=="BROray-Light" and .name==$name and
      .policySha256==$policySha and .serializationProfile=="dynamic-bounded-v1" and
      .upstream.scheme=="http" and (.upstream.host|type)=="string" and
      .upstream.port==8080 and .domain=="ndns" and .sslRedirect==true and
      .securityLevel=="public" and (.ndnsBase|type)=="string" and
      (.publicFqdn|type)=="string" and (.lighttpdConfigSha256|type)=="string" and
      ([.serialization.domain,.serialization.sslRedirect,.serialization.securityLevel] |
       all(.=="present" or .=="omitted"))
    ' "$OWNER" >/dev/null 2>&1 || return 1
    host="$(jq -r '.upstream.host' "$OWNER")"
    config_sha="$(jq -r '.lighttpdConfigSha256' "$OWNER")"
    ipv4_valid "$host" && [ "${#config_sha}" -eq 64 ]
}

owner_host()
{
    owner_valid || return 1
    jq -r '.upstream.host' "$OWNER"
}

owner_config_sha()
{
    owner_valid || return 1
    jq -r '.lighttpdConfigSha256' "$OWNER"
}

owned_state_exact()
{
    config="$1"
    owner_valid || return 1
    host="$(owner_host)" || return 1
    config_sha="$(owner_config_sha)" || return 1
    domain_state="$(jq -r '.serialization.domain' "$OWNER")"
    ssl_state="$(jq -r '.serialization.sslRedirect' "$OWNER")"
    security_state="$(jq -r '.serialization.securityLevel' "$OWNER")"
    serialization_valid "$domain_state" && serialization_valid "$ssl_state" &&
    serialization_valid "$security_state" || return 1
    config_owned_exact "$host" "$config_sha" &&
    proxy_exact "$config" "$host" "$domain_state" "$ssl_state" "$security_state"
}

apply_proxy()
{
    host="$1"
    for command_text in \
        "ip http proxy $NAME" \
        "ip http proxy $NAME upstream http $host $PORT" \
        "ip http proxy $NAME domain ndns" \
        "ip http proxy $NAME ssl redirect" \
        "ip http proxy $NAME security-level public"
    do
        run_ndmc "$command_text" >/dev/null 2>&1 || return 1
    done
}

verify_proxy_exact_live()
{
    host="$1"
    config="$APP_ROOT/tmp/web-publish-verify.$$.conf"
    running_config "$config" || return 1
    proxy_exact "$config" "$host"
    rc=$?
    rm -f "$config"
    return "$rc"
}

verify_proxy_absent_live()
{
    config="$APP_ROOT/tmp/web-publish-absent.$$.conf"
    running_config "$config" || return 1
    if proxy_exists "$config"; then rc=1; else rc=0; fi
    rm -f "$config"
    return "$rc"
}

wait_proxy_exact()
{
    host="$1"; attempt=1
    while [ "$attempt" -le "$VERIFY_ATTEMPTS" ]; do
        verify_proxy_exact_live "$host" && return 0
        [ "$attempt" -ge "$VERIFY_ATTEMPTS" ] || sleep "$VERIFY_DELAY"
        attempt=$((attempt + 1))
    done
    return 1
}

wait_proxy_absent()
{
    attempt=1
    while [ "$attempt" -le "$VERIFY_ATTEMPTS" ]; do
        verify_proxy_absent_live && return 0
        [ "$attempt" -ge "$VERIFY_ATTEMPTS" ] || sleep "$VERIFY_DELAY"
        attempt=$((attempt + 1))
    done
    return 1
}

save_exact()
{
    host="$1"
    run_ndmc 'system configuration save' >/dev/null 2>&1 && wait_proxy_exact "$host"
}

save_absent()
{
    run_ndmc 'system configuration save' >/dev/null 2>&1 && wait_proxy_absent
}

owner_write()
{
    host="$1"
    ndns_base="$2"
    config="$APP_ROOT/tmp/web-publish-owner-profile.$$.conf"
    running_config "$config" || return 1
    profile="$(proxy_profile "$config" "$host")" || { rm -f "$config"; return 1; }
    rm -f "$config"
    domain_state="$(printf '%s\n' "$profile" | awk -F '\t' 'NF==3{print $1}')"
    ssl_state="$(printf '%s\n' "$profile" | awk -F '\t' 'NF==3{print $2}')"
    security_state="$(printf '%s\n' "$profile" | awk -F '\t' 'NF==3{print $3}')"
    policy_sha="$(broray_light_web_policy_sha256)" || return 1
    config_sha="$(sha256_file "$LIGHTTPD_CONFIG")" || return 1
    temporary="$OWNER.new.$$"
    jq -n --arg name "$NAME" --arg policySha "$policy_sha" --arg host "$host" \
      --arg ndnsBase "$ndns_base" --arg publicFqdn "$NAME.$ndns_base" \
      --arg configSha "$config_sha" --arg domainState "$domain_state" \
      --arg sslState "$ssl_state" --arg securityState "$security_state" \
      --arg updatedAt "$(date '+%Y-%m-%dT%H:%M:%S%z')" '
      {schemaVersion:1,owner:"BROray-Light",name:$name,policySha256:$policySha,
       serializationProfile:"dynamic-bounded-v1",upstream:{scheme:"http",host:$host,port:8080},
       domain:"ndns",sslRedirect:true,securityLevel:"public",ndnsBase:$ndnsBase,
       publicFqdn:$publicFqdn,lighttpdConfigSha256:$configSha,
       serialization:{domain:$domainState,sslRedirect:$sslState,securityLevel:$securityState},
       updatedAt:$updatedAt}' >"$temporary" || { rm -f "$temporary"; return 1; }
    chmod 600 "$temporary" 2>/dev/null || true
    mv -f "$temporary" "$OWNER"
}

recovery_mark()
{
    temporary="$RECOVERY.new.$$"
    jq -n --arg stage "$1" --arg updatedAt "$(date '+%Y-%m-%dT%H:%M:%S%z')" \
      '{schemaVersion:1,state:"recovery-required",path:"web-publish",failedStage:$stage,updatedAt:$updatedAt}' \
      >"$temporary" 2>/dev/null || return 1
    chmod 600 "$temporary" 2>/dev/null || true
    mv -f "$temporary" "$RECOVERY"
}

restore_files()
{
    config_backup="$1"; owner_backup="$2"; owner_existed="$3"
    cp -p "$config_backup" "$LIGHTTPD_CONFIG" || return 1
    if [ "$owner_existed" = true ]; then
        cp -p "$owner_backup" "$OWNER" || return 1
    else
        rm -f "$OWNER"
    fi
}

rollback_state()
{
    initial="$1"; old_host="$2"; config_backup="$3"; owner_backup="$4"; owner_existed="$5"
    restore_files "$config_backup" "$owner_backup" "$owner_existed" || return 1
    if [ "$initial" = owned ]; then
        apply_proxy "$old_host" && wait_proxy_exact "$old_host" && save_exact "$old_host"
    else
        run_ndmc "no ip http proxy $NAME" >/dev/null 2>&1 && wait_proxy_absent && save_absent
    fi
}

transaction_fail()
{
    stage="$1"; initial="$2"; old_host="$3"; config_backup="$4"; owner_backup="$5"; owner_existed="$6"
    web_error "$stage" TRANSACTION_FAILED 'Web publication transaction failed; rollback required.'
    rollback_state "$initial" "$old_host" "$config_backup" "$owner_backup" "$owner_existed" || {
        recovery_mark "$stage" >/dev/null 2>&1 || true
        web_error rollback ROLLBACK_FAILED 'Rollback was not proven; recovery marker created.'
    }
    return 1
}

ensure_publication()
{
    [ ! -e "$RECOVERY" ] && [ ! -L "$RECOVERY" ] || {
        web_error ensure-preflight RECOVERY_REQUIRED 'Prior transaction requires recovery.'
        return 1
    }
    mkdir -p "$APP_ROOT/tmp" "$APP_ROOT/config" || return 1
    host="$(broray_light_web_detect_lan_ip)" || {
        web_error ensure-preflight LAN_IP_AMBIGUOUS 'Exactly one private configured/live LAN address is required.'
        return 1
    }
    ndns_base="$(ndns_identity)" || {
        web_error ensure-preflight NDNS_UNAVAILABLE 'KeenDNS cloud identity is unavailable or ambiguous.'
        return 1
    }
    before="$APP_ROOT/tmp/web-publish-before.$$.conf"
    config_backup="$APP_ROOT/tmp/web-publish-lighttpd-before.$$.conf"
    owner_backup="$APP_ROOT/tmp/web-publish-owner-before.$$.json"
    running_config "$before" || return 1
    cp -p "$LIGHTTPD_CONFIG" "$config_backup" || { rm -f "$before"; return 1; }
    owner_existed=false
    if [ -e "$OWNER" ] || [ -L "$OWNER" ]; then
        owner_valid || { rm -f "$before" "$config_backup"; web_error ensure-preflight RECEIPT_INVALID 'Receipt is invalid.'; return 1; }
        cp -p "$OWNER" "$owner_backup" || { rm -f "$before" "$config_backup"; return 1; }
        owner_existed=true
    fi
    if proxy_exists "$before"; then
        owned_state_exact "$before" || {
            rm -f "$before" "$config_backup" "$owner_backup"
            web_error ensure-preflight OWNERSHIP_MISMATCH 'Existing brolight object is foreign or differs from its receipt.'
            return 1
        }
        old_host="$(owner_host)" || return 1
        if [ "$old_host" = "$host" ]; then
            rm -f "$before" "$config_backup" "$owner_backup"
            printf 'https://%s.%s/\n' "$NAME" "$ndns_base"
            return 0
        fi
        initial=owned
    else
        if [ "$owner_existed" = true ]; then
            rm -f "$before" "$config_backup" "$owner_backup"
            web_error ensure-preflight RECEIPT_LIVE_MISMATCH 'Receipt exists but live brolight object is absent.'
            return 1
        fi
        config_prepare_initial || {
            rm -f "$before" "$config_backup"
            web_error ensure-preflight CONFIG_NOT_ADOPTABLE 'Lighttpd config is not the exact canonical loopback seed.'
            return 1
        }
        initial=absent
        old_host=127.0.0.1
    fi
    rm -f "$before"
    policy_require ensure-mutation || { rm -f "$config_backup" "$owner_backup"; return 1; }
    config_set_bind "$host" "$old_host" || {
        rm -f "$config_backup" "$owner_backup"
        web_error ensure-bind CONFIG_BIND_FAILED 'Failed to stage exact LAN bind.'
        return 1
    }
    apply_proxy "$host" && wait_proxy_exact "$host" && save_exact "$host" &&
    owner_write "$host" "$ndns_base" || {
        transaction_fail ensure-apply "$initial" "$old_host" "$config_backup" "$owner_backup" "$owner_existed" || true
        rm -f "$config_backup" "$owner_backup"
        return 1
    }
    final="$APP_ROOT/tmp/web-publish-final.$$.conf"
    running_config "$final" && owned_state_exact "$final" || {
        rm -f "$final"
        transaction_fail ensure-final "$initial" "$old_host" "$config_backup" "$owner_backup" "$owner_existed" || true
        rm -f "$config_backup" "$owner_backup"
        return 1
    }
    rm -f "$final" "$config_backup" "$owner_backup"
    printf 'https://%s.%s/\n' "$NAME" "$ndns_base"
}

status_publication()
{
    config="$APP_ROOT/tmp/web-publish-status.$$.conf"
    mkdir -p "$APP_ROOT/tmp" || return 1
    running_config "$config" || return 1
    owned_state_exact "$config" || { rm -f "$config"; return 1; }
    rm -f "$config"
    jq -r '"https://" + .publicFqdn + "/"' "$OWNER"
}

delete_publication()
{
    config="$APP_ROOT/tmp/web-publish-delete.$$.conf"
    mkdir -p "$APP_ROOT/tmp" || return 1
    running_config "$config" || return 1
    if ! proxy_exists "$config"; then
        rm -f "$config"
        [ ! -e "$OWNER" ] && [ ! -L "$OWNER" ]
        return $?
    fi
    owned_state_exact "$config" || { rm -f "$config"; web_error delete OWNERSHIP_MISMATCH 'Foreign brolight object will not be deleted.'; return 1; }
    rm -f "$config"
    policy_require delete || return 1
    run_ndmc "no ip http proxy $NAME" >/dev/null 2>&1 && wait_proxy_absent && save_absent || return 1
    rm -f "$OWNER"
}

case "${1:-}" in
    ensure) ensure_publication ;;
    status) status_publication ;;
    delete) delete_publication ;;
    *) echo 'Usage: broray-light-web-publish {ensure|status|delete}' >&2; exit 1 ;;
esac
