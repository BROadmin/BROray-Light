#!/usr/bin/env python3
"""Live exact-r1 updater RAM namespace handoff and rollback, no router writes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from test_r0013_r1_admission import R1Fixture, RAM, ADMISSION, inventory, ENGINE_SHA

JOURNAL = ADMISSION.with_name('lifecycle-r1-journal.sh')
HANDOFF = ADMISSION.with_name('lifecycle-r1-ram.sh')


def call(shell, env, action):
    code = '. "$1"; . "$2"; . "$3"; . "$4"; '+action
    return subprocess.run([*shell, '-c', code, 'fixture', str(RAM), str(ADMISSION), str(JOURNAL), str(HANDOFF)],
                          env=env, capture_output=True, text=True, timeout=20)


def callback(mode):
    root = Path(os.environ['BRORAY_LIGHT_ROOT_PREFIX'])
    shell = json.loads(os.environ['R0013_FIXTURE_SHELL'])
    old = root / 'tmp/broray-light-updater'
    receipt = root / 'opt/var/lib/broray-light-updater/legacy-transition.json'
    old_before = inventory(old)
    old_inode = old.stat().st_ino
    if mode == 'extra-old-file':
        old.joinpath('foreign').write_bytes(b'preserve\n')
    elif mode == 'foreign-app-namespace':
        app_ram = root / 'tmp/broray-light'
        app_ram.mkdir(mode=0o700)
        app_ram.joinpath('unknown').write_bytes(b'preserve\n')
    result = call(shell, os.environ, 'brl_r1_ram_promote')
    report = dict(returncode=result.returncode, stderr=result.stderr)
    if mode == 'extra-old-file':
        assert result.returncode == 1 and 'LEGACY_WORK_SHAPE' in result.stderr, report
        assert old.stat().st_ino == old_inode and old.joinpath('foreign').read_bytes() == b'preserve\n'
    elif mode == 'foreign-app-namespace':
        assert result.returncode == 1 and 'RAM_NAMESPACE' in result.stderr, report
        restored = call(shell, os.environ, 'brl_r1_ram_restore')
        assert restored.returncode == 0, restored.stderr
        assert old.stat().st_ino == old_inode and inventory(old) == old_before
        assert app_ram.joinpath('unknown').read_bytes() == b'preserve\n'
    else:
        assert result.returncode == 0, report
        data = json.loads(receipt.read_text())['ramTransition']
        private = root / 'tmp' / data['directory']
        saved = private / 'updater-r1'
        assert saved.stat().st_ino == old_inode and inventory(saved) == old_before
        assert old.stat().st_ino != old_inode and old.stat().st_mode & 0o777 == 0o700
        assert old.joinpath('owner').read_text().strip() == 'BROray-Light:updater-runtime/1'
        assert private.stat().st_mode & 0o777 == 0o700 and private.parent == root / 'tmp'
        before = inventory(root)
        again = call(shell, os.environ, 'brl_r1_ram_promote')
        assert again.returncode == 0 and inventory(root) == before, (again.returncode, again.stderr)
        fenced = call(shell, os.environ, 'brl_lock_acquire global')
        assert fenced.returncode == 2 and inventory(root) == before, 'Legacy fence was bypassed'
        if mode.startswith('refuse-'):
            restore_fixture = None
            if mode == 'refuse-backup-tamper':
                path = saved / 'archive.list'
                content = path.read_bytes()
                path.write_bytes(b'tampered\n')
                restore_fixture = lambda: path.write_bytes(content)
            elif mode == 'refuse-new-symlink':
                real = private / 'fixture-new-namespace'
                old.rename(real)
                old.symlink_to(real, target_is_directory=True)
                def restore_fixture():
                    old.unlink()
                    real.rename(old)
            elif mode == 'refuse-new-operation':
                path = old / 'request.lock'
                path.mkdir(mode=0o700)
                path.joinpath('foreign').write_bytes(b'preserve\n')
                def restore_fixture():
                    path.joinpath('foreign').unlink()
                    path.rmdir()
            elif mode == 'refuse-private-owner':
                path = private / 'owner'
                content = path.read_bytes()
                path.write_bytes(b'foreign-owner\n')
                restore_fixture = lambda: path.write_bytes(content)
            before = inventory(root)
            refused = call(shell, os.environ, 'brl_r1_ram_restore')
            assert refused.returncode == 1 and inventory(root) == before, (refused.returncode, refused.stderr)
            restore_fixture()
        if mode == 'resume-old-moved':
            # Model kill after publishing new namespaces but before receipt.
            record = json.loads(receipt.read_text())
            record['ramTransition']['phase'] = 'old-moved'
            del record['ramTransition']['newWorkId']
            receipt.write_text(json.dumps(record))
            resumed = call(shell, os.environ, 'brl_r1_ram_promote')
            assert resumed.returncode == 0, resumed.stderr
        if mode == 'resume-restoring':
            # Model kill after moving the new namespace aside, before receipt.
            old.rename(private / 'updater-new')
        if mode != 'commit':
            if mode != 'resume-restoring':
                old.joinpath('work/retained-diagnostics').write_bytes(b'new-ram-data\n')
            restored = call(shell, os.environ, 'brl_r1_ram_restore')
            assert restored.returncode == 0, restored.stderr
            assert old.stat().st_ino == old_inode and inventory(old) == old_before
            assert json.loads(receipt.read_text())['ramTransition']['phase'] == 'restored'
            if mode != 'resume-restoring':
                assert private.joinpath('updater-new/work/retained-diagnostics').read_bytes() == b'new-ram-data\n'
            before = inventory(root)
            again = call(shell, os.environ, 'brl_r1_ram_restore')
            assert again.returncode == 0 and inventory(root) == before
        report['phase'] = json.loads(receipt.read_text())['ramTransition']['phase']
    (root / 'admission-result.json').write_text(json.dumps(report))
    return 1 if mode != 'commit' else 0


class RamFixture(R1Fixture):
    def __init__(self, shell, mode):
        super().__init__(shell, 'valid')
        command = ' '.join(shlex.quote(x) for x in [sys.executable, '-B', str(Path(__file__).resolve()), '--callback', mode])
        hook = '''#!/bin/sh
if [ "$1" = start ] && [ "$(readlink "$2/current")" = releases/2.0.0-r1 ]; then
    exec CALLBACK
fi
exit 0
'''.replace('CALLBACK', command)
        self.write(self.executable / 'service', hook.encode(), 0o755)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--shell', default='/bin/dash')
    parser.add_argument('--busybox', action='store_true')
    parser.add_argument('--busybox-tools', action='store_true')
    parser.add_argument('--result', type=Path)
    parser.add_argument('--callback')
    args = parser.parse_args()
    if args.callback:
        try: result=callback(args.callback)
        except Exception as error:
            import traceback
            record=dict(callbackFailure=True,error=str(error),traceback=traceback.format_exc())
            (Path(os.environ['BRORAY_LIGHT_ROOT_PREFIX'])/'admission-result.json').write_text(json.dumps(record))
            raise SystemExit(1)
        raise SystemExit(result)
    assert os.geteuid() == 0, 'Root on disposable Linux CI only'
    shell = [args.shell, 'ash'] if args.busybox else [args.shell]
    if args.busybox_tools:
        import r0013_busybox_fixture
        utility_fixture = r0013_busybox_fixture.enable()
    report = dict(stage='R0013', revision='p49-work-shape-diagnostic-and-callback-evidence',
                  scope='REAL_R1_ENGINE_LIVE_RAM_HANDOFF_FIXTURE_APP_SERVICE', engineSha256=ENGINE_SHA,
                  handoffSha256=hashlib.sha256(HANDOFF.read_bytes()).hexdigest(), shell=shell,
                  utilities='BusyBox applets' if args.busybox_tools else 'host utilities', tests=[])
    failed = False
    for mode in ('commit', 'rollback', 'extra-old-file', 'foreign-app-namespace',
                 'refuse-backup-tamper', 'refuse-new-symlink', 'refuse-new-operation',
                 'refuse-private-owner', 'resume-old-moved', 'resume-restoring'):
        fixture = RamFixture(shell, mode)
        try:
            before = fixture.persistent()
            result = fixture.update(0 if mode == 'commit' else 1)
            assert not result.get('callbackFailure'),result
            assert fixture.current() == ('2.0.0-r1' if mode == 'commit' else '1.0.0-r1')
            assert fixture.persistent() == before
            # r1 retains its own cleanup authority; our handoff never deletes its locks.
            assert not (fixture.root / 'opt/var/lock/broray-light/global-operation.lock').exists()
            assert not (fixture.root / 'opt/var/lock/broray-light-updater/request.lock').exists()
            report['tests'].append(dict(name=mode, status='PASS', callback=result))
        except Exception as error:
            report['tests'].append(dict(name=mode, status='FAIL', error=str(error)))
            failed = True
            break
        finally:
            fixture.close()
    report['status'] = 'FAIL_FIRST_ERROR' if failed else 'PASS_RAM_NAMESPACE_HANDOFF_AND_RESTORE'
    payload = (json.dumps(report, indent=2)+'\n').encode()
    if args.result:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_bytes(payload)
    print(payload.decode())
    if args.busybox_tools: utility_fixture.cleanup()
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
