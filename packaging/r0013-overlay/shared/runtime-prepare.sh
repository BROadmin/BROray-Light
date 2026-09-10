#!/opt/bin/ash
set -eu
ROOT="${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/broray-light"
legacy_root="${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/var/lock"
legacy_receipt="${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/var/lib/broray-light-updater/legacy-transition.json"
if [ -e "$legacy_receipt" ] || [ -L "$legacy_receipt" ] ||
    [ -e "$legacy_root/broray-light/global-operation.lock" ] || [ -L "$legacy_root/broray-light/global-operation.lock" ] ||
    [ -e "$legacy_root/broray-light-updater/request.lock" ] || [ -L "$legacy_root/broray-light-updater/request.lock" ]; then
    legacy_entry="$ROOT/releases/2.0.0-r1/app/share/lifecycle/helpers/lifecycle-r1-entry.sh"
    [ -f "$legacy_entry" ] && [ ! -L "$legacy_entry" ] && [ "$(stat -c '%u:%a:%h' "$legacy_entry")" = 0:644:1 ] || exit 1
    . "$legacy_entry" || exit 1
    legacy_rc=0
    brl_r1_entry prepare || legacy_rc=$?
    case "$legacy_rc" in 0) ;; 10) exit 0 ;; *) exit 1 ;; esac
fi
. "$ROOT/lib/runtime-environment.sh" || exit 1

fail()
{
    printf 'BROray-Light runtime preparation refused: %s\n' "$*" >&2
    exit 1
}

# Legacy cache-policy conversions are not needed for the sole accepted source
# r1. They staged a config on the same filesystem; moving that old algorithm's
# scratch to tmpfs would lose its atomic-publication assumption. The coordinated
# lifecycle owns config+receipt migration; normal startup only checks them.
for directory in backup config config/system servers subscriptions runtime; do
    path="$ROOT/$directory"
    if [ ! -e "$path" ] && [ ! -L "$path" ]; then (umask 077; mkdir "$path") || fail 'durable directory creation failed'; fi
    [ -d "$path" ] && [ ! -L "$path" ] || fail 'ambiguous durable directory'
    case "$(stat -c '%u:%a' "$path")" in 0:700|0:755) ;; *) fail 'unsafe durable directory ownership' ;; esac
done
for seed in settings.json server-auto-switch.json lighttpd.conf version; do
    case "$seed" in settings.json|server-auto-switch.json) path="$ROOT/config/system/$seed" ;; *) path="$ROOT/config/$seed" ;; esac
    if [ ! -e "$path" ] && [ ! -L "$path" ]; then
        (umask 077; set -C; cat "$ROOT/share/defaults/$seed" > "$path") || fail 'default seed creation failed'
    fi
    [ -f "$path" ] && [ ! -L "$path" ] && [ -s "$path" ] || fail 'invalid durable configuration file'
    case "$(stat -c '%u:%a' "$path")" in 0:600|0:644) ;; *) fail 'unsafe configuration ownership' ;; esac
done
config="$ROOT/config/lighttpd.conf"
grep -Fqx 'server.pid-file = "/tmp/broray-light/run/lighttpd.pid"' "$config" &&
    grep -Fqx 'server.errorlog = "/tmp/broray-light/logs/lighttpd-error.log"' "$config" &&
    grep -Fqx 'server.modules = ( "mod_cgi", "mod_setenv" )' "$config" &&
    grep -Fqx '$HTTP["url"] =~ "(^/$|\.html$)" {' "$config" || fail 'runtime/cache configuration requires coordinated lifecycle migration'
owner="$ROOT/config/web-publish.json"
if [ -e "$owner" ] || [ -L "$owner" ]; then
    [ -f "$owner" ] && [ ! -L "$owner" ] || fail 'ambiguous publication receipt'
    sha="$(sha256sum "$config" | awk '{print $1}')"
    jq -e --arg sha "$sha" '.owner=="BROray-Light" and .name=="brolight" and .lighttpdConfigSha256==$sha' \
        "$owner" >/dev/null || fail 'publication receipt does not bind this configuration'
fi
"$ROOT/bin/broray-subscriptions" deduplicate >/dev/null
