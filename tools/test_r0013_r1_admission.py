#!/usr/bin/env python3
"""Read-only transition admission under the EXACT unchanged r1 updater.

Real signed fixture transactions; no actual application/platform migration yet.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time

import r0013_inputs as inputs
from test_r0013_updater_ram import Fixture, NEW, OLD

REPO = Path(__file__).resolve().parents[1]
RAM = REPO / 'packaging/r0013-overlay/shared/runtime-ram.sh'
ADMISSION = REPO / 'packaging/r0013-overlay/shared/lifecycle-r1-admission.sh'
ENGINE_SHA = '773aaf37893ab100e7023d63c8061d8c4763a4d6186844bb3b671d758c145743'


def inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        st = path.lstat()
        value = os.readlink(path) if path.is_symlink() else hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        result[str(path.relative_to(root))] = [st.st_ino, st.st_mode, value]
    return result


def check(root, shell):
    before = inventory(root)
    code = '. "$1"; . "$2"; brl_r1_transition_admitted'
    process = subprocess.run([*shell, '-c', code, 'fixture', str(RAM), str(ADMISSION)],
                             env=os.environ, text=True, capture_output=True, timeout=10)
    assert inventory(root) == before, 'Admission check mutated the isolated root'
    return dict(returncode=process.returncode, stdout=process.stdout, stderr=process.stderr)


def callback(mode):
    root = Path(os.environ['BRORAY_LIGHT_ROOT_PREFIX'])
    shell = json.loads(os.environ['R0013_FIXTURE_SHELL'])
    app = root / 'opt/broray-light'
    slot = app / 'releases' / NEW
    paths = {
        'wrong-lock-owner': root / 'opt/var/lock/broray-light/global-operation.lock/pid',
        'wrong-operation': root / 'opt/var/lock/broray-light-updater/request.lock/operation',
        'wrong-phase': root / 'opt/var/lib/broray-light-updater/transaction.json',
        'tampered-slot': slot / 'app/lib/test.sh',
        'changed-engine': root / 'opt/libexec/broray-light-updater/broray-light-updater.sh',
    }
    restore = None
    if mode in paths:
        path = paths[mode]
        payload, permissions = path.read_bytes(), path.stat().st_mode & 0o777
        if mode == 'wrong-lock-owner': changed = b'99999999\n'
        elif mode == 'wrong-operation': changed = b'check\n'
        elif mode == 'wrong-phase':
            transaction = json.loads(payload)
            transaction['phase'] = 'prepared'
            changed = json.dumps(transaction).encode()
        else: changed = payload+b'\n# deliberate fixture corruption\n'
        # Atomic replacement keeps the live r1 interpreter's open inode intact.
        staged = path.with_name(path.name+'.fixture')
        staged.write_bytes(changed)
        staged.chmod(permissions)
        staged.replace(path)
        def restore():
            staged.write_bytes(payload)
            staged.chmod(permissions)
            staged.replace(path)
    elif mode == 'foreign-coowner':
        path = root / 'opt/broray'
        path.symlink_to('missing')
        def restore(): path.unlink()
    elif mode == 'absolute-current':
        path = app / 'current'
        original = os.readlink(path)
        path.unlink()
        path.symlink_to(slot, target_is_directory=True)
        def restore():
            path.unlink()
            path.symlink_to(original, target_is_directory=True)
    elif mode == 'world-writable-work':
        path = root / 'tmp/broray-light-updater'
        permissions = path.stat().st_mode & 0o777
        path.chmod(0o777)
        def restore(): path.chmod(permissions)
    try:
        result = check(root, shell)
        (root / 'admission-result.json').write_text(json.dumps(result))
        if mode == 'pause':
            (root / 'admission-paused').write_text('ready')
            deadline = time.monotonic()+15
            while not (root / 'admission-continue').exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            assert (root / 'admission-continue').exists(), 'Parent did not release fixture callback'
    finally:
        if restore: restore()
    return result['returncode']


class R1Fixture(Fixture):
    def __init__(self, shell, mode):
        super().__init__(shell)
        self.engine = self.root / 'opt/libexec/broray-light-updater/broray-light-updater.sh'
        payload = inputs.git_bytes('updater/opt/libexec/broray-light-updater/broray-light-updater.sh')
        assert hashlib.sha256(payload).hexdigest() == ENGINE_SHA
        self.write(self.engine, payload, 0o755)
        self.env['R0013_FIXTURE_SHELL'] = json.dumps(shell)
        self.update_options = ['update', '--json']
        command = ' '.join(shlex.quote(x) for x in [sys.executable, '-B', str(Path(__file__).resolve()), '--callback', mode])
        hook = '''#!/bin/sh
if [ "$1" = start ] && [ "$(readlink "$2/current")" = releases/2.0.0-r1 ]; then
    exec CALLBACK
fi
exit 0
'''.replace('CALLBACK', command)
        self.write(self.executable / 'service', hook.encode(), 0o755)

    def update(self, expected=0):
        result = subprocess.run([*self.shell, str(self.engine), *self.update_options], env=self.env,
                                capture_output=True, text=True, timeout=20)
        assert result.returncode == expected, (result.returncode, result.stdout, result.stderr)
        assert hashlib.sha256(self.engine.read_bytes()).hexdigest() == ENGINE_SHA
        return json.loads((self.root / 'admission-result.json').read_text())


def cases():
    yield 'exact_live_r1_signed_transaction_admitted_read_only', 'valid', None
    yield 'exact_live_r1_cli_without_json_is_still_supported', 'cli', None
    yield 'unrecognized_update_argument_is_refused', 'bad-argv', 'NOT_UPDATER_CHILD'
    for mode, error in [('wrong-lock-owner', 'LOCK_OWNER_MISMATCH'),
                        ('wrong-operation', 'LOCK_SHAPE'), ('wrong-phase', 'TRANSACTION'),
                        ('tampered-slot', 'SLOT_MANIFEST'), ('changed-engine', 'ENGINE_IDENTITY'),
                        ('foreign-coowner', 'COOWNERSHIP'), ('absolute-current', 'CURRENT_BINDING'),
                        ('world-writable-work', 'CONTAINER_OWNERSHIP')]:
        yield mode, mode, error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--shell', default='/bin/dash')
    parser.add_argument('--busybox', action='store_true')
    parser.add_argument('--busybox-tools', action='store_true')
    parser.add_argument('--result', type=Path)
    parser.add_argument('--callback')
    args = parser.parse_args()
    if args.callback:
        raise SystemExit(callback(args.callback))
    assert os.geteuid() == 0, 'Root in disposable Linux CI only'
    shell = [args.shell, 'ash'] if args.busybox else [args.shell]
    if args.busybox_tools:
        import r0013_busybox_fixture
        utility_fixture = r0013_busybox_fixture.enable()
    report = dict(stage='R0013', revision='p27-exact-r1-webui-json-argv-compatibility',
                  scope='READ_ONLY_ADMISSION_REAL_R1_ENGINE_TEST_SIGNATURES_FIXTURE_APP_SERVICE',
                  engineSha256=ENGINE_SHA, admissionSha256=hashlib.sha256(ADMISSION.read_bytes()).hexdigest(),
                  shell=shell, utilities='BusyBox applets' if args.busybox_tools else 'host utilities', tests=[])
    failed = False
    for name, mode, error in cases():
        fixture = R1Fixture(shell, mode)
        if mode == 'cli': fixture.update_options = ['update']
        elif mode == 'bad-argv': fixture.update_options.append('--force')
        try:
            before = fixture.persistent()
            result = fixture.update(1 if error else 0)
            assert result['returncode'] == (1 if error else 0), result
            if error:
                assert 'BRORAY_LIGHT_MIGRATION_REFUSED:'+error in result['stderr'], result
                assert fixture.current() == OLD
            else:
                assert fixture.current() == NEW
            assert fixture.persistent() == before
            report['tests'].append(dict(name=name, status='PASS'))
        except Exception as exc:
            report['tests'].append(dict(name=name, status='FAIL', error=str(exc)))
            failed = True
            break
        finally:
            fixture.close()
    if not failed:
        fixture = R1Fixture(shell, 'pause')
        try:
            child = subprocess.Popen([*shell, str(fixture.engine), *fixture.update_options], env=fixture.env,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
            fixture.children.append(child)
            deadline = time.monotonic()+10
            while not (fixture.root / 'admission-paused').exists() and child.poll() is None and time.monotonic()<deadline:
                time.sleep(0.02)
            assert (fixture.root / 'admission-paused').exists(), 'r1 transaction did not reach paused callback'
            # This process is a sibling of the updater, not its child.
            code = '. "$1"; . "$2"; brl_r1_transition_admitted'
            before = inventory(fixture.root)
            outsider = subprocess.run([*shell, '-c', code, 'fixture', str(RAM), str(ADMISSION)],
                                      env=fixture.env, capture_output=True, text=True, timeout=10)
            assert outsider.returncode == 1 and 'NOT_UPDATER_CHILD' in outsider.stderr, outsider.stderr
            assert inventory(fixture.root) == before
            (fixture.root / 'admission-continue').write_text('continue')
            out, err = child.communicate(timeout=10)
            assert child.returncode == 0, (out, err)
            report['tests'].append(dict(name='unrelated_caller_cannot_borrow_live_r1_locks', status='PASS'))
        except Exception as exc:
            report['tests'].append(dict(name='unrelated_caller_cannot_borrow_live_r1_locks', status='FAIL', error=str(exc)))
            failed = True
        finally:
            fixture.close()
    report['status'] = 'FAIL_FIRST_ERROR' if failed else 'PASS_READ_ONLY_ADMISSION'
    payload = (json.dumps(report, indent=2)+'\n').encode()
    if args.result:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_bytes(payload)
    print(payload.decode())
    if args.busybox_tools: utility_fixture.cleanup()
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
