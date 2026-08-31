#!/opt/bin/ash

# Exact r23 private-interface/live-address intersection semantics, scoped to
# package-owned BROray-Light WebUI publication.

BRORAY_LIGHT_WEB_ROOT="${BRORAY_LIGHT_WEB_ROOT:-/opt/broray-light}"
BRORAY_LIGHT_WEB_NDMC="${BRORAY_LIGHT_WEB_NDMC:-ndmc}"
BRORAY_LIGHT_WEB_IP="${BRORAY_LIGHT_WEB_IP:-ip}"

broray_light_web_ipv4_valid()
{
    printf '%s\n' "${1:-}" | awk -F. '
      NF==4 {
        for(i=1;i<=4;i++) if($i!~/^[0-9]+$/ || $i<0 || $i>255) exit 1
        if (!($1==10 || ($1==172 && $2>=16 && $2<=31) || ($1==192 && $2==168))) exit 1
        ok=1
      }
      END{exit ok?0:1}'
}

broray_light_web_scratch_retire()
{
    scratch="$1"
    scratch_root="$2"
    case "$scratch" in "$scratch_root"/broray-light-web-network.*) ;; *) return 1 ;; esac
    [ -d "$scratch" ] && [ ! -L "$scratch" ] || return 1
    rm -f "$scratch/running" "$scratch/running.err" \
        "$scratch/configured-private.addresses" "$scratch/live" \
        "$scratch/live.err" "$scratch/live.addresses" "$scratch/matches" \
        2>/dev/null || true
    rmdir "$scratch"
}

broray_light_web_network_diagnostic()
{
    printf 'BRORAY_LIGHT_WEB_LAN_DIAG code=%s configured_private=%s live_ipv4=%s matches=%s\n' \
        "$1" "$2" "$3" "$4" >&2
}

broray_light_web_detect_lan_ip()
{
    configured_count=unknown
    live_address_count=unknown
    match_count=unknown
    if [ -n "${BRORAY_LIGHT_WEB_LAN_IP_OVERRIDE:-}" ]; then
        [ "${BRORAY_LIGHT_WEB_TEST_MODE:-0}" = 1 ] || return 1
        lan_ip="$BRORAY_LIGHT_WEB_LAN_IP_OVERRIDE"
    else
        command -v "$BRORAY_LIGHT_WEB_NDMC" >/dev/null 2>&1 || {
            broray_light_web_network_diagnostic NDMC_UNAVAILABLE "$configured_count" "$live_address_count" "$match_count"
            return 1
        }
        command -v "$BRORAY_LIGHT_WEB_IP" >/dev/null 2>&1 || {
            broray_light_web_network_diagnostic IP_UNAVAILABLE "$configured_count" "$live_address_count" "$match_count"
            return 1
        }
        scratch_root="${BRORAY_LIGHT_WEB_TMP_ROOT:-$BRORAY_LIGHT_WEB_ROOT/tmp}"
        [ -d "$scratch_root" ] && [ ! -L "$scratch_root" ] || {
            broray_light_web_network_diagnostic SCRATCH_ROOT_UNSAFE "$configured_count" "$live_address_count" "$match_count"
            return 1
        }
        scratch="$(mktemp -d "$scratch_root/broray-light-web-network.XXXXXXXXXX")" || {
            broray_light_web_network_diagnostic SCRATCH_CREATE_FAILED "$configured_count" "$live_address_count" "$match_count"
            return 1
        }
        [ -d "$scratch" ] && [ ! -L "$scratch" ] || return 1
        running="$scratch/running"
        live="$scratch/live"
        matches="$scratch/matches"
        "$BRORAY_LIGHT_WEB_NDMC" -c 'show running-config' >"$running" 2>"$running.err" || {
            broray_light_web_scratch_retire "$scratch" "$scratch_root" || true
            broray_light_web_network_diagnostic RUNNING_SNAPSHOT_FAILED "$configured_count" "$live_address_count" "$match_count"
            return 1
        }
        "$BRORAY_LIGHT_WEB_IP" -4 addr show >"$live" 2>"$live.err" || {
            broray_light_web_scratch_retire "$scratch" "$scratch_root" || true
            broray_light_web_network_diagnostic LIVE_SNAPSHOT_FAILED "$configured_count" "$live_address_count" "$match_count"
            return 1
        }
        awk '
          function valid(v, p,i) {
            if (v !~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/) return 0
            split(v,p,".")
            for(i=1;i<=4;i++) if(p[i]<0 || p[i]>255) return 0
            return p[1]==10 || (p[1]==172 && p[2]>=16 && p[2]<=31) || (p[1]==192 && p[2]==168)
          }
          function flush(i) {
            if (in_interface && security_count==1 && private_count==1)
              for (i=1; i<=address_count; i++) print address[i]
            in_interface=0; security_count=0; private_count=0; address_count=0
          }
          {
            raw=$0; line=raw; sub(/^[[:space:]]*/,"",line)
            n=split(line,f,/[[:space:]]+/)
            if (raw !~ /^[[:space:]]/) {
              flush()
              if (n==2 && f[1]=="interface" && f[2] ~ /^[A-Za-z][A-Za-z0-9_-]*$/) in_interface=1
              next
            }
            if (!in_interface) next
            if (n==2 && f[1]=="security-level") {
              security_count++; if (f[2]=="private") private_count++; next
            }
            if (n>=3 && f[1]=="ip" && f[2]=="address" && valid(f[3])) address[++address_count]=f[3]
          }
          END {flush()}
        ' "$running" | sort -u >"$scratch/configured-private.addresses" || {
            broray_light_web_scratch_retire "$scratch" "$scratch_root" || true
            return 1
        }
        awk '/inet / {v=$2; sub(/\/.*/,"",v); print v}' "$live" | sort -u >"$live.addresses" || {
            broray_light_web_scratch_retire "$scratch" "$scratch_root" || true
            return 1
        }
        configured_count="$(wc -l <"$scratch/configured-private.addresses" | tr -d ' ')"
        live_address_count="$(wc -l <"$live.addresses" | tr -d ' ')"
        awk 'NR==FNR {live[$1]=1; next} live[$1] {print $1}' \
            "$live.addresses" "$scratch/configured-private.addresses" | sort -u >"$matches" || {
            broray_light_web_scratch_retire "$scratch" "$scratch_root" || true
            return 1
        }
        match_count="$(wc -l <"$matches" | tr -d ' ')"
        [ "$match_count" = 1 ] || {
            broray_light_web_scratch_retire "$scratch" "$scratch_root" || true
            broray_light_web_network_diagnostic MATCH_COUNT_NOT_ONE "$configured_count" "$live_address_count" "$match_count"
            return 1
        }
        lan_ip="$(sed -n '1p' "$matches")"
        broray_light_web_scratch_retire "$scratch" "$scratch_root" || return 1
    fi
    broray_light_web_ipv4_valid "$lan_ip" || {
        broray_light_web_network_diagnostic RESULT_NOT_RFC1918 "$configured_count" "$live_address_count" "$match_count"
        return 1
    }
    if [ "${BRORAY_LIGHT_WEB_TEST_MODE:-0}" != 1 ]; then
        live_count="$("$BRORAY_LIGHT_WEB_IP" -4 addr show 2>/dev/null | awk -v wanted="$lan_ip" '
          /inet / {value=$2; sub(/\/.*/,"",value); if(value==wanted)n++}
          END{print n+0}')"
        [ "$live_count" = 1 ] || {
            broray_light_web_network_diagnostic LIVE_BINDING_COUNT_NOT_ONE "$configured_count" "$live_address_count" "$live_count"
            return 1
        }
    fi
    printf '%s\n' "$lan_ip"
}

