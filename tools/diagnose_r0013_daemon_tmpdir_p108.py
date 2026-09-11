"""Read only the daemon's TMPDIR/PATH, never its full environment."""
import json
from diagnose_r0013_xray_compatibility import Target, REPO
p=REPO/'checkpoints/R0013/DAEMON-TMPDIR-P108.json';assert not p.exists()
t=Target()
try:
  v=t.command('''set -eu
pid=$(cat /tmp/broray-light/run/broray-lightd.pid)
case "$pid" in ''|*[!0-9]*) exit 1;; esac
test -r /proc/$pid/environ
tr '\\000' '\\n' </proc/$pid/environ | sed -n '/^TMPDIR=/p; /^PATH=/p'
tmp=$(tr '\\000' '\\n' </proc/$pid/environ | sed -n 's/^TMPDIR=//p')
case "$tmp" in /tmp/broray-light-install.*/opkg) ;; *) exit 42;; esac
test ! -e "$tmp"
printf 'INHERITED_INSTALLER_TMPDIR_ALREADY_REMOVED\\n'
TMPDIR="$tmp" /opt/bin/ash -c '. /opt/broray-light/lib/runtime-environment.sh; . /opt/broray-light/lib/interface-core.sh; broray_interface_value type'
''',timeout=20,check=False)
  report={'schemaVersion':1,'revision':'p108-inherited-installer-tmpdir-diagnosis','observation':v,'candidateReady':False}
  p.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps(report,ensure_ascii=False))
finally:t.client.close()
