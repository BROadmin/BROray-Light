#!/opt/bin/ash
set -eu
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH
umask 077
for p in /opt /opt/etc /opt/etc/init.d /opt/libexec /opt/share /opt/var /opt/var/lib; do
 [ -d "$p" ] && [ ! -L "$p" ] && [ "$(stat -c %u "$p")" = 0 ]
done
[ ! -e /opt/broray ] && [ ! -L /opt/broray ]
[ ! -e /tmp/broray-bootstrap.lock ] && [ ! -L /tmp/broray-bootstrap.lock ]
[ ! -e /opt/var/lib/broray-opkg ]
if [ -r /proc/2214/stat ]; then
 [ "$(sed 's/^.*) //' /proc/2214/stat | awk '{print $20}')" != 252733 ] || exit 1
fi
jq -e '.contract=="broray-universal-platform-handoff/1" and .state=="success" and .running==false' /opt/var/lib/broray-platform-handoff/status.json >/dev/null
[ -d /opt/libexec/broray-bootstrap ] && [ ! -L /opt/libexec/broray-bootstrap ] && [ "$(stat -c %u /opt/libexec/broray-bootstrap)" = 0 ]
[ "$(find /opt/libexec/broray-bootstrap -mindepth 1 -maxdepth 1 | wc -l)" -eq 1 ]
[ -d /opt/share/broray-bootstrap ] && [ ! -L /opt/share/broray-bootstrap ] && [ "$(stat -c %u /opt/share/broray-bootstrap)" = 0 ]
[ "$(find /opt/share/broray-bootstrap -mindepth 1 -maxdepth 1 | wc -l)" -eq 3 ]
[ -d /opt/var/lib/broray-bootstrap ] && [ ! -L /opt/var/lib/broray-bootstrap ] && [ "$(stat -c %u /opt/var/lib/broray-bootstrap)" = 0 ]
[ "$(find /opt/var/lib/broray-bootstrap -mindepth 1 -maxdepth 1 | wc -l)" -eq 2 ]
[ -d /opt/var/lib/broray-platform-handoff ] && [ ! -L /opt/var/lib/broray-platform-handoff ] && [ "$(stat -c %u /opt/var/lib/broray-platform-handoff)" = 0 ]
[ "$(find /opt/var/lib/broray-platform-handoff -mindepth 1 -maxdepth 1 | wc -l)" -eq 5 ]
verify_file()
{
 [ -f "$1" ] && [ ! -L "$1" ] && [ "$(stat -c '%u:%h' "$1")" = 0:1 ]
 [ "$(sha256sum "$1" | awk '{print $1}')" = "$2" ]
}
verify_file '/opt/etc/init.d/S99broray-bootstrap' '5be46ba9880a48b595806dfad1193cb75ef0674171f76dcbdd031859e6df0643'
verify_file '/opt/libexec/broray-bootstrap/run.sh' 'f66d1d1eba6a95e1c4b6317d5c14ac27ca0e44a7a3b2c72de3fa047262d2792a'
verify_file '/opt/var/lib/broray-bootstrap/attempted-manifest-sha256' '61ef6f440dae207c2609fe5218a3b8858ebd5a5e4caf59ef58b7cc3563da92be'
verify_file '/opt/var/lib/broray-bootstrap/status' '3374540fce4605ab1ac7d3a6564226f4b5d1e6cf517fe42c313b53f1de221877'
verify_file '/opt/var/lib/broray-platform-handoff/status.json' '5893b58c5c9585b0d208043168c8f6294ba39bc69e9d8ea4ca5cd7d763675816'
verify_file '/opt/var/lib/broray-platform-handoff/request.json' 'e3581f384ff0ad0a5d7271a0fe8353cd46facef238ab9fd140476bc0061a8118'
verify_file '/opt/var/lib/broray-platform-handoff/daemon-was-running' 'a17fcf0a2f50e2d495e4f90ce263410edc183add6c62699a2facbccf60410f74'
verify_file '/opt/var/lib/broray-platform-handoff/worker.pid' 'a5886eb7a8bd35b5281988dc7838152303e904409a5c07f2b184f5b28b684ca4'
verify_file '/opt/var/lib/broray-platform-handoff/phase' '37a40f08d8548dba289b9b0bb35bcf63b359f6d37ee86044ebc6b6da080b9ec1'
verify_file '/opt/share/broray-bootstrap/manifest.json' '99d4f99272ac1e7440dbab62507bbc741ec1323913b9cfce606caddfad74a0f0'
verify_file '/opt/share/broray-bootstrap/manifest.sig' '0129c01ec747a8e6433aa0a8ce8eb1f4803ba41173a218eebd2e6bef00d59205'
verify_file '/opt/share/broray-bootstrap/broray-bootstrap-rsa3072-v1-public.pem' 'fbf1178a4eb16d1f8269f7e67e54df6d501355ed7c26d59f70e6b7f8cf527d79'
printf 'PRECHECK_PASS_12_EXACT_BACKED_UP_FILES\n'
verify_file '/opt/etc/init.d/S99broray-bootstrap' '5be46ba9880a48b595806dfad1193cb75ef0674171f76dcbdd031859e6df0643' && rm '/opt/etc/init.d/S99broray-bootstrap'
verify_file '/opt/libexec/broray-bootstrap/run.sh' 'f66d1d1eba6a95e1c4b6317d5c14ac27ca0e44a7a3b2c72de3fa047262d2792a' && rm '/opt/libexec/broray-bootstrap/run.sh'
verify_file '/opt/var/lib/broray-bootstrap/attempted-manifest-sha256' '61ef6f440dae207c2609fe5218a3b8858ebd5a5e4caf59ef58b7cc3563da92be' && rm '/opt/var/lib/broray-bootstrap/attempted-manifest-sha256'
verify_file '/opt/var/lib/broray-bootstrap/status' '3374540fce4605ab1ac7d3a6564226f4b5d1e6cf517fe42c313b53f1de221877' && rm '/opt/var/lib/broray-bootstrap/status'
verify_file '/opt/var/lib/broray-platform-handoff/status.json' '5893b58c5c9585b0d208043168c8f6294ba39bc69e9d8ea4ca5cd7d763675816' && rm '/opt/var/lib/broray-platform-handoff/status.json'
verify_file '/opt/var/lib/broray-platform-handoff/request.json' 'e3581f384ff0ad0a5d7271a0fe8353cd46facef238ab9fd140476bc0061a8118' && rm '/opt/var/lib/broray-platform-handoff/request.json'
verify_file '/opt/var/lib/broray-platform-handoff/daemon-was-running' 'a17fcf0a2f50e2d495e4f90ce263410edc183add6c62699a2facbccf60410f74' && rm '/opt/var/lib/broray-platform-handoff/daemon-was-running'
verify_file '/opt/var/lib/broray-platform-handoff/worker.pid' 'a5886eb7a8bd35b5281988dc7838152303e904409a5c07f2b184f5b28b684ca4' && rm '/opt/var/lib/broray-platform-handoff/worker.pid'
verify_file '/opt/var/lib/broray-platform-handoff/phase' '37a40f08d8548dba289b9b0bb35bcf63b359f6d37ee86044ebc6b6da080b9ec1' && rm '/opt/var/lib/broray-platform-handoff/phase'
verify_file '/opt/share/broray-bootstrap/manifest.json' '99d4f99272ac1e7440dbab62507bbc741ec1323913b9cfce606caddfad74a0f0' && rm '/opt/share/broray-bootstrap/manifest.json'
verify_file '/opt/share/broray-bootstrap/manifest.sig' '0129c01ec747a8e6433aa0a8ce8eb1f4803ba41173a218eebd2e6bef00d59205' && rm '/opt/share/broray-bootstrap/manifest.sig'
verify_file '/opt/share/broray-bootstrap/broray-bootstrap-rsa3072-v1-public.pem' 'fbf1178a4eb16d1f8269f7e67e54df6d501355ed7c26d59f70e6b7f8cf527d79' && rm '/opt/share/broray-bootstrap/broray-bootstrap-rsa3072-v1-public.pem'
rmdir '/opt/libexec/broray-bootstrap'
rmdir '/opt/share/broray-bootstrap'
rmdir '/opt/var/lib/broray-bootstrap'
rmdir '/opt/var/lib/broray-platform-handoff'
printf 'P78_RETIRED_S99_BOOTSTRAP_AND_COMPLETED_HANDOFF\n'
