#!/opt/bin/ash
set -eu
PATH=/opt/bin:/opt/sbin:/opt/usr/bin:/opt/usr/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH
umask 077
[ "$(id -u)" = 0 ]
[ -d /tmp ] && [ ! -L /tmp ]
awk '$2=="/tmp" && $3=="tmpfs" {ok=1} END{exit !ok}' /proc/mounts
[ "$(find -P /tmp -maxdepth 0 -type d -uid 0 -printf '%m')" = 1777 ]
work="$(mktemp -d /tmp/brl-r13-backup-p73.XXXXXX)"
[ "$(find -P "$work" -maxdepth 0 -type d -uid 0 -printf '%m')" = 700 ]
printf 'R0013 P73 private target backup\n' >"$work/owner"
printf '%s\n' "$work"
set --
for path in /opt/broray /opt/etc /opt/lib/opkg /opt/libexec/broray-* /opt/var/lib/broray* /opt/bin/broray*; do
    if [ -e "$path" ] || [ -L "$path" ]; then set -- "$@" "${path#/}"; fi
done
printf '%s\n' "$@" >"$work/roots.txt"
find /opt/broray/config /opt/broray/servers /opt/broray/subscriptions /opt/broray/runtime -type f -exec sha256sum '{}' + | sort >"$work/persistent-before.sha256"
/opt/usr/bin/tar --exclude='opt/broray/run' --exclude='opt/broray/logs' --exclude='opt/broray/tmp' --exclude='opt/broray/update' -czf "$work/full-broray.tar.gz" -C / "$@"
/opt/usr/bin/gzip -t "$work/full-broray.tar.gz"
find /opt/broray/config /opt/broray/servers /opt/broray/subscriptions /opt/broray/runtime -type f -exec sha256sum '{}' + | sort >"$work/persistent-after.sha256"
cmp "$work/persistent-before.sha256" "$work/persistent-after.sha256"
/bin/ndmc -c 'show running-config' >"$work/running-config.txt"
[ -s "$work/running-config.txt" ]
printf '%s\n' "$SSH_CONNECTION" >"$work/ssh-connection.txt"
chmod 600 "$work/"*
(cd "$work" && sha256sum full-broray.tar.gz running-config.txt roots.txt persistent-before.sha256 persistent-after.sha256 ssh-connection.txt)
printf 'P73_BACKUP_PASS\n'
