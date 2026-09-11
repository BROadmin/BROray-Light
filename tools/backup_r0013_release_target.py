"""Verified private backup before authorized final target replacement/control tests."""
import base64
import hashlib
import json
from pathlib import Path
import re
from diagnose_r0013_xray_compatibility import Target, REPO

out = REPO / 'dist/R0013/private-target/p93'
assert not out.exists()
out.mkdir()
target = Target()
record = {'schemaVersion': 1, 'revision': 'p93-private-backup-v1', 'status': 'IN_PROGRESS', 'candidateReady': False, 'files': []}
receipt = REPO / 'checkpoints/R0013/TARGET-BACKUP-P93.json'
assert not receipt.exists()


def save():
    receipt.write_bytes((json.dumps(record, indent=2) + '\n').encode())


save()
try:
    work = target.command('''set -eu; umask 077
test "$(stat -f -c %T /tmp)" = tmpfs
test "$(df -k /tmp | awk 'END{print $4}')" -gt 100000
test "$(readlink /opt/broray-light/current)" = releases/2.0.0-r1
(cd /opt/broray-light/current && sha256sum -c APP-SHA256SUMS >/dev/null)
mktemp -d /tmp/brl-r13-backup-p93.XXXXXX
''')['stdout'].strip()
    assert re.fullmatch(r'/tmp/brl-r13-backup-p93\.[A-Za-z0-9]{6}', work)
    record['protectedRamPath'] = work
    before = target.command("find /opt/broray-light/config /opt/broray-light/servers /opt/broray-light/subscriptions /opt/broray-light/runtime -type f -exec sha256sum '{}' + | sort | sha256sum")['stdout'].split()[0]
    target.command(f'''set -eu; umask 077
test "$(stat -c %u:%a {work})" = 0:700
tar -czf {work}/light-private.tar.gz -C / opt/broray-light/config opt/broray-light/servers opt/broray-light/subscriptions opt/broray-light/runtime opt/var/lib/broray-light opt/var/lib/broray-light-updater
gzip -t {work}/light-private.tar.gz
/bin/ndmc -c 'show running-config' >{work}/running-config.txt
test -s {work}/running-config.txt
''', timeout=60)
    for name in ('light-private.tar.gz', 'running-config.txt'):
        expected = target.command('sha256sum ' + work + '/' + name)['stdout'].split()[0]
        raw = base64.b64decode(target.command('base64 ' + work + '/' + name, timeout=90)['stdout'])
        assert hashlib.sha256(raw).hexdigest() == expected
        (out / name).write_bytes(raw)
        record['files'].append({'privateLocalPath': (out / name).relative_to(REPO).as_posix(), 'sha256': expected, 'bytes': len(raw)})
    after = target.command("find /opt/broray-light/config /opt/broray-light/servers /opt/broray-light/subscriptions /opt/broray-light/runtime -type f -exec sha256sum '{}' + | sort | sha256sum")['stdout'].split()[0]
    assert before == after, 'durable data changed during backup; stop before mutation'
    target.command(f'''set -eu
test ! -L {work}; test "$(stat -c %u:%a {work})" = 0:700
rm -- {work}/light-private.tar.gz {work}/running-config.txt
rmdir {work}
''')
    record.update(status='PASS_PRIVATE_VERIFIED_BACKUP', durableStateSha256=before, ramScratchRemoved=True, routerConfigurationChanged=False)
except Exception as error:
    record.update(status='FAIL_FIRST_ERROR', errorType=type(error).__name__, nextExactAction='DIAGNOSE_BACKUP_FAILURE_BEFORE_MUTATION')
    raise
finally:
    save()
    target.client.close()
print(json.dumps(record, indent=2))
