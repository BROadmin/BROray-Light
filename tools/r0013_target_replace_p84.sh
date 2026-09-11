#!/opt/bin/ash
set -eu
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH
umask 077
STAGE=/tmp/brl-r13-install-p76.E7rJwm
[ "$(stat -c '%u:%a:%d:%i' "$STAGE")" = 0:700:13:45373386 ]
[ "$(readlink /opt/broray-light/current)" = releases/2.0.0-r1 ]
[ "$(sha256sum /opt/broray-light/current/APP-SHA256SUMS | awk '{print $1}')" = 91b949910948897d3c62a3fc1b47b108f8cd6cb76c6b4f41bb8f83a8763a95bc ]
(cd /opt/broray-light/current && sha256sum -c APP-SHA256SUMS >/dev/null)
[ "$(sha256sum "$STAGE/broray-light-install-2.0.0-p83.sh" | awk '{print $1}')" = f8775988803ed70fd1eed455a6444e567ebad8109a252c430a7071f4aefda0c2 ]
[ "$(sha256sum "$STAGE/broray-light_2.0.0-p83_aarch64-3.10.ipk" | awk '{print $1}')" = a31449263dfc5b772854fcd3f4d8624c334e3038715c61ae9996fd4fcd6adb79 ]
[ -z "$(find /opt/broray-light/servers /opt/broray-light/subscriptions -type f)" ]
/opt/bin/broray-light-web-publishctl status >/dev/null
find /opt/broray-light/config /opt/broray-light/runtime /opt/broray-light/servers /opt/broray-light/subscriptions -type f -exec sha256sum '{}' + | sort >"$STAGE/p84-durable-before.sha256"
printf 'P84_PRECHECK_PASS\n'
/opt/etc/init.d/S24broray-light stop
/opt/etc/init.d/S23broray-light-updater stop
printf 'P84_EXPLICIT_STOP_PASS\n'
for proc in /proc/[0-9]*/exe; do
 [ -L "$proc" ] || continue
 case "$(readlink "$proc")" in /opt/broray-light/*|/tmp/broray-light/run/web-new/native-auth/*) echo 'ERROR: owned executable still running' >&2; exit 1;; esac
done
# The shell processes are identified by the exact argv path, not a substring
# search of this script's stdin or a broad killall operation.
for proc in /proc/[0-9]*/cmdline; do
 [ -r "$proc" ] || continue
 if tr '\000' '\n' <"$proc" 2>/dev/null | grep -Ex '/opt/broray-light/bin/(broray-lightd|broray-home-snapshot)' >/dev/null; then
  echo 'ERROR: owned app shell still running' >&2; exit 1
 fi
done
mkdir "$STAGE/opkg-remove-p84"
TMPDIR="$STAGE/opkg-remove-p84" opkg --tmp-dir "$STAGE/opkg-remove-p84" remove broray-light
[ -z "$(opkg status broray-light)" ]
[ -L /opt/broray-light/current ] && [ "$(readlink /opt/broray-light/current)" = releases/2.0.0-r1 ]
[ ! -e /opt/broray-light/current/app/lib/runtime-environment.sh ]
# Only this exact package-owned selector is retired; durable files stay.
rm /opt/broray-light/current
printf 'P84_PRIOR_PACKAGE_REMOVED_DURABLE_STATE_RETAINED\n'
BRORAY_LIGHT_PACKAGE_FILE="$STAGE/broray-light_2.0.0-p83_aarch64-3.10.ipk" /opt/bin/ash "$STAGE/broray-light-install-2.0.0-p83.sh"
find /opt/broray-light/config /opt/broray-light/runtime /opt/broray-light/servers /opt/broray-light/subscriptions -type f -exec sha256sum '{}' + | sort >"$STAGE/p84-durable-after.sha256"
cmp "$STAGE/p84-durable-before.sha256" "$STAGE/p84-durable-after.sha256"
rmdir "$STAGE/opkg-remove-p84"
/opt/etc/init.d/S24broray-light status
/opt/etc/init.d/S23broray-light-updater status
printf 'P84_CORRECTED_PACKAGE_INSTALLED_AND_DURABLE_HASHES_PRESERVED\n'
