#!/usr/bin/env python3
"""P18: real updater/signatures/tar/tmpfs; fixture app slots and service boundary.

This is not a complete installed-r1 lifecycle or physical-router acceptance.
The signing key is ephemeral test-only and never the production trust identity.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import tarfile
import tempfile
import time

REPO = Path(__file__).resolve().parents[1]
OVERLAY = REPO / 'packaging/r0013-overlay'
UPDATER = OVERLAY / 'system/updater/opt/libexec/broray-light-updater/broray-light-updater.sh'
OLD, NEW = '1.0.0-r1', '2.0.0-r1'


class Fixture:
    def __init__(self, shell):
        self.temp = tempfile.TemporaryDirectory(prefix='r0013-updater-', dir='/dev/shm')
        self.exec_temp = tempfile.TemporaryDirectory(prefix='r0013-updater-hooks-', dir='/var/tmp')
        self.root, self.executable = Path(self.temp.name), Path(self.exec_temp.name)
        self.shell = shell
        self.children = []
        (self.root / 'tmp').mkdir(mode=0o1777)
        (self.root / 'tmp').chmod(0o1777)
        (self.root / 'opt/var/lib').mkdir(parents=True)
        self.app = self.root / 'opt/broray-light'
        self.durable = self.root / 'opt/var/lib/broray-light-updater'
        self.ram = self.root / 'tmp/broray-light-updater'
        (self.app / 'releases').mkdir(parents=True)
        for name in ('config', 'servers', 'subscriptions', 'runtime'):
            (self.app / name).mkdir(mode=0o700)
        self.write(self.app / 'config/version', (OLD+'\n').encode())
        self.write(self.app / 'config/settings.json', b'{"preserve":"config"}\n')
        self.write(self.app / 'servers/list.json', b'{"preserve":"servers"}\n')
        self.write(self.app / 'subscriptions/list.json', b'{"preserve":"subscriptions"}\n')
        self.write(self.app / 'runtime/xray', b'#!/bin/sh\necho existing-xray\n', 0o755)
        self.make_slot(OLD)
        (self.app / 'current').symlink_to('releases/'+OLD, target_is_directory=True)
        (self.app / 'bin').symlink_to('current/app/bin', target_is_directory=True)
        self.write(self.root / 'opt/libexec/broray-light-updater/runtime-ram.sh',
                   (OVERLAY / 'shared/runtime-ram.sh').read_bytes())
        self.key = self.root / 'test-only.key'
        self.pub = self.root / 'test-only.pub'
        subprocess.run(['minisign', '-G', '-W', '-s', str(self.key), '-p', str(self.pub)],
                       check=True, capture_output=True, timeout=10)
        self.write(self.executable / 'service', b'''#!/bin/sh
printf '%s\n' "$1" >> "$BRORAY_LIGHT_ROOT_PREFIX/service.calls"
if [ "$1" = start ] && [ "${FIXTURE_PAUSE_START:-0}" = 1 ]; then
    printf paused > "$BRORAY_LIGHT_ROOT_PREFIX/service.paused"
    while :; do sleep 1; done
fi
exit 0
''', 0o755)
        self.write(self.executable / 'health', b'''#!/bin/sh
[ "$1" != "${FIXTURE_HEALTH_FAIL:-none}" ]
''', 0o755)
        self.env = dict(os.environ, BRORAY_LIGHT_ROOT_PREFIX=str(self.root),
                        BRORAY_LIGHT_TEST_MODE='1', BRORAY_LIGHT_SIGNATURE_BIN='/usr/bin/minisign',
                        BRORAY_LIGHT_PUBLIC_KEY=str(self.pub),
                        BRORAY_LIGHT_SERVICE_HOOK=str(self.executable / 'service'),
                        BRORAY_LIGHT_HEALTH_HOOK=str(self.executable / 'health'))
        self.slot = self.make_slot(NEW, installed=False)
        self.bundle = self.root / 'bundle.tar.gz'
        self.archive()
        self.index()

    def write(self, path, payload, mode=0o600):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        path.chmod(mode)

    def make_slot(self, release, installed=True):
        slot = self.app / 'releases' / release if installed else self.root / 'candidate-slot'
        payloads = {'bin/broray': b'#!/bin/sh\nexit 0\n',
                    'bin/broray-runtime-prepare': b'#!/bin/sh\nexit 0\n',
                    'lib/test.sh': b'# fixture only\n',
                    'share/defaults/version': (release+'\n').encode(),
                    'web-new/home.html': b'fixture home\n'}
        for name, data in payloads.items():
            self.write(slot / 'app' / name, data, 0o755 if name.startswith('bin/') else 0o644)
        meta = dict(product='BROray-Light', releaseId=release, candidateId=release)
        self.write(slot / 'release.json', json.dumps(meta).encode())
        self.write(slot / 'SLOT-MANIFEST.json', json.dumps(meta).encode())
        sums = ''.join(hashlib.sha256(data).hexdigest()+'  app/'+name+'\n' for name, data in sorted(payloads.items()))
        self.write(slot / 'APP-SHA256SUMS', sums.encode())
        return slot

    def archive(self, extra=None):
        with tarfile.open(self.bundle, 'w:gz') as archive:
            for path in sorted(self.slot.rglob('*')):
                if path.is_file():
                    archive.add(path, arcname=path.relative_to(self.slot).as_posix(), recursive=False)
            if extra:
                member, payload = extra
                archive.addfile(member, io.BytesIO(payload) if member.isfile() else None)

    def index(self, release=NEW, bad_hash=False):
        payload = self.bundle.read_bytes()
        files = [p for p in (self.slot / 'app').rglob('*') if p.is_file()]
        value = dict(schemaVersion=1, product='BROray-Light', channel='stable',
                     candidate=dict(releaseId=release, candidateId=release, architecture='aarch64-3.10',
                                    bundle=dict(url=self.bundle.as_uri(), sizeBytes=len(payload),
                                                sha256='0'*64 if bad_hash else hashlib.sha256(payload).hexdigest()),
                                    appSlot=dict(fileCount=len(files), logicalBytes=sum(p.stat().st_size for p in files))))
        index = self.root / 'release.json'
        self.write(index, json.dumps(value).encode())
        subprocess.run(['minisign', '-S', '-W', '-s', str(self.key), '-m', str(index),
                        '-x', str(index)+'.minisig'], check=True, capture_output=True, timeout=10)
        self.env['BRORAY_LIGHT_RELEASE_INDEX_URL'] = index.as_uri()

    def run(self, command, expected=0):
        result = subprocess.run([*self.shell, str(UPDATER), command], env=self.env,
                                capture_output=True, text=True, timeout=15)
        assert result.returncode == expected, (command, result.returncode, result.stdout, result.stderr)
        return result

    def current(self):
        return json.loads((self.app / 'current/release.json').read_text())['releaseId']

    def persistent(self):
        return {str(p.relative_to(self.app)): p.read_bytes() for folder in ('config', 'servers', 'subscriptions', 'runtime')
                for p in (self.app / folder).rglob('*') if p.is_file() and p != self.app / 'config/version'}

    def clean_work(self):
        assert not list((self.ram / 'work').iterdir()), 'download/extraction work leaked'
        assert not (self.ram / 'request.lock').exists(), 'request lock leaked'
        assert not list((self.root / 'tmp/broray-light/run/locks').iterdir()), 'global/admission leaked'
        assert not (self.durable / 'state.json').exists(), 'operational status is persistent'
        assert not (self.root / 'opt/var/lock').exists(), 'persistent locks created'

    def close(self):
        for child in self.children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.communicate(timeout=10)
        self.temp.cleanup()
        self.exec_temp.cleanup()


def cases():
    def update(f):
        before = f.persistent()
        result = json.loads(f.run('update').stdout)
        assert result['installedReleaseId'] == NEW and result['previousReleaseId'] == OLD
        assert f.current() == NEW and f.persistent() == before
        assert (f.app / 'releases' / OLD).is_dir()
        assert not (f.durable / 'transaction.json').exists()
        assert json.loads((f.ram / 'state.json').read_text())['stage'] == 'complete'
        f.clean_work()
    yield 'signed_update_and_user_xray_previous_slot_persistence', update

    def equal(f):
        update(f)
        before = (f.root / 'service.calls').read_bytes()
        assert json.loads(f.run('update').stdout)['relation'] == 'equal'
        assert (f.root / 'service.calls').read_bytes() == before
        f.clean_work()
    yield 'equal_version_is_no_op_without_service_restart', equal

    def downgrade(f):
        update(f)
        f.index(OLD)
        f.run('update', 20)
        assert f.current() == NEW
        assert json.loads((f.ram / 'state.json').read_text())['errorCode'] == 'DOWNGRADE_REFUSED'
        f.clean_work()
    yield 'signed_downgrade_refusal', downgrade

    def rollback(f):
        before = f.persistent()
        f.env['FIXTURE_HEALTH_FAIL'] = NEW
        f.run('update', 1)
        assert f.current() == OLD and f.persistent() == before
        assert (f.app / 'config/version').read_text().strip() == OLD
        assert json.loads((f.durable / 'transaction.json').read_text())['phase'] == 'rolled-back'
        assert json.loads((f.ram / 'state.json').read_text())['errorCode'] == 'POST_SWITCH_HEALTH_FAILED'
        f.clean_work()
        f.run('recover')
        assert not (f.durable / 'transaction.json').exists()
        f.clean_work()
    yield 'forced_health_failure_rolls_back_and_recovers_receipt', rollback

    def signature(f):
        f.write(f.root / 'release.json', b'{}')
        f.run('update', 1)
        assert f.current() == OLD and not (f.root / 'service.calls').exists()
        assert json.loads((f.ram / 'state.json').read_text())['errorCode'] == 'INDEX_VERIFY_FAILED'
        f.clean_work()
    yield 'altered_signed_index_refused_before_service_stop', signature

    def bundle_hash(f):
        f.index(bad_hash=True)
        f.run('update', 1)
        assert f.current() == OLD and not (f.root / 'service.calls').exists()
        assert json.loads((f.ram / 'state.json').read_text())['errorCode'] == 'BUNDLE_VERIFY_FAILED'
        f.clean_work()
    yield 'signed_wrong_bundle_hash_refused', bundle_hash

    def unsafe(f, kind):
        payload = b'bad'
        member = tarfile.TarInfo('app/bin/broray' if kind == 'duplicate' else '../escaped' if kind == 'traversal' else 'app/link')
        member.size = len(payload)
        if kind in ('symlink', 'hardlink'):
            member.type = tarfile.SYMTYPE if kind == 'symlink' else tarfile.LNKTYPE
            member.linkname = '/etc/passwd'
        f.archive((member, payload))
        f.index()
        f.run('update', 1)
        assert f.current() == OLD and not (f.root / 'service.calls').exists()
        assert not (f.root / 'escaped').exists()
        assert json.loads((f.ram / 'state.json').read_text())['errorCode'] == 'ARCHIVE_UNSAFE'
        f.clean_work()
    for kind in ('duplicate', 'traversal', 'symlink', 'hardlink'):
        yield 'signed_' + kind + '_archive_refused', lambda f, kind=kind: unsafe(f, kind)

    def bad_manifest(f, duplicate):
        path = f.slot / 'APP-SHA256SUMS'
        payload = path.read_bytes()
        f.write(path, payload + (payload.splitlines()[0]+b'\n' if duplicate else b'0'*64+b'  ../../outside\n'))
        f.archive()
        f.index()
        f.run('update', 1)
        assert f.current() == OLD and not (f.root / 'service.calls').exists()
        assert json.loads((f.ram / 'state.json').read_text())['errorCode'] == 'SLOT_INVALID'
        f.clean_work()
    yield 'manifest_traversal_rejected_before_hash_reads', lambda f: bad_manifest(f, False)
    yield 'manifest_duplicate_refused', lambda f: bad_manifest(f, True)

    def full_owner(f):
        (f.root / 'opt/broray').symlink_to('absent')
        f.run('update', 1)
        assert not f.ram.exists() and f.current() == OLD
    yield 'dangling_full_product_ownership_refused_before_ram_write', full_owner

    def interrupted(f):
        f.env['FIXTURE_PAUSE_START'] = '1'
        child = subprocess.Popen([*f.shell, str(UPDATER), 'update'], env=f.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, start_new_session=True)
        f.children.append(child)
        deadline = time.monotonic()+10
        while not (f.root / 'service.paused').exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert (f.root / 'service.paused').exists(), child.communicate(timeout=2)
        os.killpg(child.pid, signal.SIGKILL)
        child.communicate(timeout=10)
        assert json.loads((f.durable / 'transaction.json').read_text())['phase'] == 'target-active'
        f.env.pop('FIXTURE_PAUSE_START')
        f.env['FIXTURE_HEALTH_FAIL'] = NEW
        f.run('recover')
        assert f.current() == OLD and not (f.durable / 'transaction.json').exists()
        # Interrupted invocation work is preserved, not silently adopted/deleted.
        assert len(list((f.ram / 'work').iterdir())) == 1
        assert not (f.ram / 'request.lock').exists()
    yield 'interrupted_target_active_recovers_previous_slot_with_stale_locks', interrupted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--shell', default='/bin/dash')
    parser.add_argument('--busybox', action='store_true')
    parser.add_argument('--result', type=Path)
    args = parser.parse_args()
    assert os.geteuid() == 0, 'Disposable root Linux CI only'
    shell = [args.shell, 'ash'] if args.busybox else [args.shell]
    report = dict(stage='R0013', revision='p20-interruption-fixture-explicit-pipes', scope='REAL_UPDATER_SIGNATURES_TMPFS_FIXTURE_SLOTS_SERVICE_BOUNDARY',
                  sourceSha256=hashlib.sha256(UPDATER.read_bytes()).hexdigest(), shell=shell, tests=[])
    failed = False
    for name, test in cases():
        fixture = Fixture(shell)
        try:
            test(fixture)
            report['tests'].append(dict(name=name, status='PASS'))
        except Exception as error:
            report['tests'].append(dict(name=name, status='FAIL', error=str(error)))
            failed = True
            break
        finally:
            fixture.close()
    report['status'] = 'FAIL_FIRST_ERROR' if failed else 'PASS_BOUNDED_CORE'
    payload = (json.dumps(report, indent=2)+'\n').encode()
    if args.result:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_bytes(payload)
    print(payload.decode())
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
