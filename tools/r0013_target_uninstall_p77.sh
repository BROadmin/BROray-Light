#!/opt/bin/ash
set -eu
PATH=/opt/bin:/opt/sbin:/opt/usr/bin:/opt/usr/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH
umask 077
[ "$(stat -c '%u:%a:%d:%i' /tmp/brl-r13-install-p76.E7rJwm)" = 0:700:13:45373386 ]
[ "$(sha256sum /opt/broray/current/app/lib/broray-page.sh | awk '{print $1}')" = 7b7d92a97674a9e3a58a31fd93bd5ed51f0fe58779a7adbdf35e0294584f0232 ]
[ "$(sha256sum /tmp/brl-r13-install-p76.E7rJwm/broray-light_2.0.0_aarch64-3.10.ipk | awk '{print $1}')" = 5b142793c7318c3620c494160d8c4413f44467e5e4d1e5e6e614fb88e142f7a7 ]
find /opt/broray/config /opt/broray/servers /opt/broray/subscriptions /opt/broray/runtime -type f -exec sha256sum '{}' + | sort > /tmp/brl-r13-install-p76.E7rJwm/pre-uninstall-persistent.sha256
cmp /tmp/brl-r13-backup-p74.mBfUv5/persistent-before.sha256 /tmp/brl-r13-install-p76.E7rJwm/pre-uninstall-persistent.sha256
ip route get 192.168.1.123 | grep -q 'dev br0'
/opt/bin/ash /opt/broray/bin/broray-system uninstall-start full 'УДАЛИТЬ BROray ПОЛНОСТЬЮ'
