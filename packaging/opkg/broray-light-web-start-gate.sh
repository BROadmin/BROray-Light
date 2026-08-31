#!/opt/bin/ash

broray_light_web_publication_start_gate()
{
    ctl="$1"
    root="${BRORAY_ROOT:-/opt/broray-light}"
    attempts="${BRORAY_LIGHT_WEB_PUBLISH_RETRY_ATTEMPTS:-30}"
    delay="${BRORAY_LIGHT_WEB_PUBLISH_RETRY_DELAY_SECONDS:-2}"
    case "$attempts" in ''|*[!0-9]*) return 1 ;; esac
    case "$delay" in ''|*[!0-9]*) return 1 ;; esac
    [ "$attempts" -ge 1 ] && [ "$attempts" -le 60 ] || return 1
    [ "$delay" -le 10 ] || return 1
    [ -x "$ctl" ] && [ ! -L "$ctl" ] || return 1
    [ -d "$root/tmp" ] && [ ! -L "$root/tmp" ] || return 1

    error_file="$root/tmp/web-publish-start.$$.err"
    [ ! -e "$error_file" ] && [ ! -L "$error_file" ] || return 1
    attempt=1
    while [ "$attempt" -le "$attempts" ]; do
        if "$ctl" ensure >/dev/null 2>"$error_file"; then
            rm -f "$error_file"
            return 0
        fi
        cat "$error_file" >&2
        if grep -Eq '^BRORAY_LIGHT_WEB_PUBLISH_ERROR:ensure-preflight:(NDNS_UNAVAILABLE|LAN_IP_AMBIGUOUS):' "$error_file"; then
            if [ "$attempt" -lt "$attempts" ]; then
                rm -f "$error_file"
                [ "$delay" -eq 0 ] || sleep "$delay"
                attempt=$((attempt + 1))
                continue
            fi
        fi
        rm -f "$error_file"
        return 1
    done
    rm -f "$error_file"
    return 1
}
