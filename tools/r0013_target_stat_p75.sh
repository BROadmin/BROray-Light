#!/opt/bin/ash
set -eu
PATH=/opt/bin:/opt/sbin:/opt/usr/bin:/opt/usr/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH
umask 077
[ "$(id -u)" = 0 ]
[ -d /tmp ] && [ ! -L /tmp ]
awk '$2=="/tmp" && $3=="tmpfs" {ok=1} END{exit !ok}' /proc/mounts
[ "$(find -P /tmp -maxdepth 0 -type d -uid 0 -printf '%m')" = 1777 ]
for dependency in libc libssp librt libpthread; do
    opkg status "$dependency" | grep -q '^Status: install .* installed$'
done
[ ! -e /opt/libexec/stat-coreutils ] && [ ! -L /opt/libexec/stat-coreutils ]
[ "$(readlink /opt/bin/stat)" = /opt/bin/busybox ]
work="$(mktemp -d /tmp/brl-r13-stat-p75.XXXXXX)"
[ "$(find -P "$work" -maxdepth 0 -type d -uid 0 -printf '%m')" = 700 ]
identity="$(find -P "$work" -maxdepth 0 -printf '%D:%i')"
printf '%s\n' "$work"
mkdir "$work/opkg"
for file in coreutils_9.9-2_aarch64-3.10.ipk coreutils-stat_9.9-2_aarch64-3.10.ipk; do
    curl -q --proto '=https' --proto-redir '=https' --tlsv1.2 --connect-timeout 10 --max-time 60 -fsSL "https://bin.entware.net/aarch64-k3.10/$file" -o "$work/$file"
done
[ "$(wc -c <"$work/coreutils_9.9-2_aarch64-3.10.ipk" | tr -d ' ')" = 860 ]
[ "$(wc -c <"$work/coreutils-stat_9.9-2_aarch64-3.10.ipk" | tr -d ' ')" = 52481 ]
[ "$(sha256sum "$work/coreutils_9.9-2_aarch64-3.10.ipk" | awk '{print $1}')" = 80f5d41f3073aba2ea2b83bd863fdee90ff201bed6283f3a7222a864fd60c815 ]
[ "$(sha256sum "$work/coreutils-stat_9.9-2_aarch64-3.10.ipk" | awk '{print $1}')" = 9bffc2feb1cdc41f7a6c1eb089aded6694c0bc27dd318505d78158751a664614 ]
TMPDIR="$work/opkg" opkg --tmp-dir "$work/opkg" install "$work/coreutils_9.9-2_aarch64-3.10.ipk" "$work/coreutils-stat_9.9-2_aarch64-3.10.ipk"
[ "$(readlink /opt/bin/stat)" = /opt/libexec/stat-coreutils ]
[ "$(stat -c '%u:%a' "$work")" = 0:700 ]
[ "$(stat -f -c %T /tmp)" = tmpfs ]
/opt/bin/ash -c 'test "$(stat -f -c %T /tmp)" = tmpfs && test "$(stat -c %u /tmp)" = 0'
printf 'P75_STAT_CAPABILITY_PASS\n'
opkg status coreutils coreutils-stat
[ "$(find -P "$work" -maxdepth 0 -uid 0 -printf '%m:%D:%i')" = "700:$identity" ]
rm -f "$work/coreutils_9.9-2_aarch64-3.10.ipk" "$work/coreutils-stat_9.9-2_aarch64-3.10.ipk"
# Empty-only cleanup; do not recursively delete unexpected package-manager data.
rmdir "$work/opkg" "$work"
printf 'P75_RAM_CLEANUP_PASS\n'
