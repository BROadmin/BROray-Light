#!/usr/bin/env python3
"""Legacy receipt/reboot-state recovery using the exact r1 updater.

RAM loss is simulated ONLY inside an invocation-owned /dev/shm fixture.
No router, global mount, actual reboot or deployment is performed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import time

from test_r0013_r1_admission import R1Fixture, RAM, ADMISSION, inventory, ENGINE_SHA

JOURNAL = ADMISSION.with_name('lifecycle-r1-journal.sh')


def call(shell, env, action):
    code = '. "$1"; . "$2"; . "$3"; '+action
    return subprocess.run([*shell, '-c', code, 'fixture', str(RAM), str(ADMISSION), str(JOURNAL)],
                          env=env, capture_output=True, text=True, timeout=15)


def callback(mode):
    root = Path(os.environ['BRORAY_LIGHT_ROOT_PREFIX'])
    shell = json.loads(os.environ['R0013_FIXTURE_SHELL'])
    receipt = root / 'opt/var/lib/broray-light-updater/legacy-transition.json'
    if mode == 'collision':
        receipt.write_bytes(b'foreign-receipt\n')
        receipt.chmod(0o600)
    result = call(shell, os.environ, 'brl_r1_transition_record')
    report = dict(returncode=result.returncode, stderr=result.stderr)
    if result.returncode == 0:
        before = inventory(root)
        again = call(shell, os.environ, 'brl_r1_transition_record')
        assert again.returncode == 0 and inventory(root) == before, 'Receipt idempotence failed'
        live = call(shell, os.environ, 'brl_r1_locks_reconcile')
        assert live.returncode == 2 and 'LEGACY_OWNER_STILL_LIVE' in live.stderr, (live.returncode, live.stderr)
        assert inventory(root) == before, 'Live-owner reconciliation mutated state'
        report['receipt'] = json.loads(receipt.read_text())
    (root / 'admission-result.json').write_text(json.dumps(report))
    if mode == 'pause' and result.returncode == 0:
        (root / 'journal-paused').write_text('ready')
        deadline = time.monotonic()+15
        while not (root / 'journal-continue').exists() and time.monotonic()<deadline:
            time.sleep(0.02)
        assert (root / 'journal-continue').exists(), 'Parent did not release journal fixture'
    return result.returncode


class JournalFixture(R1Fixture):
    def __init__(self, shell, mode):
        super().__init__(shell, 'valid')
        self.receipt = self.durable / 'legacy-transition.json'
        self.request = self.root / 'opt/var/lock/broray-light-updater/request.lock'
        self.global_lock = self.root / 'opt/var/lock/broray-light/global-operation.lock'
        command = ' '.join(shlex.quote(x) for x in [sys.executable, '-B', str(Path(__file__).resolve()), '--callback', mode])
        hook = '''#!/bin/sh
if [ "$1" = start ] && [ "$(readlink "$2/current")" = releases/2.0.0-r1 ]; then
    exec CALLBACK
fi
exit 0
'''.replace('CALLBACK', command)
        self.write(self.executable / 'service', hook.encode(), 0o755)

    def interrupted(self):
        child = subprocess.Popen([*self.shell, str(self.engine), 'update'], env=self.env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        self.children.append(child)
        deadline = time.monotonic()+10
        while not (self.root / 'journal-paused').exists() and child.poll() is None and time.monotonic()<deadline:
            time.sleep(0.02)
        assert (self.root / 'journal-paused').exists(), child.communicate(timeout=2)
        os.killpg(child.pid, signal.SIGKILL)
        child.communicate(timeout=10)
        assert self.request.exists() and self.global_lock.exists()
        assert json.loads(self.receipt.read_text())['legacyPid'] == str(child.pid)

    def simulate_ram_loss(self):
        root = self.root.resolve()
        ram = self.root / 'tmp'
        assert root.parent == Path('/dev/shm') and root.name.startswith('r0013-updater-')
        assert not ram.is_symlink() and ram.resolve() == root / 'tmp'
        shutil.rmtree(ram)
        ram.mkdir(mode=0o1777)
        ram.chmod(0o1777)

    def reconcile(self, expected=0, error=None):
        result = call(self.shell, self.env, 'brl_r1_locks_reconcile')
        assert result.returncode == expected, (result.returncode, result.stdout, result.stderr)
        if error:
            assert error in result.stderr, result.stderr
        return result


def cases():
    def completed(f):
        result = f.update()
        assert result['returncode'] == 0 and result['receipt']['legacyLocks'] == 'owned'
        assert f.receipt.stat().st_mode & 0o777 == 0o600
        assert not f.request.exists() and not f.global_lock.exists()
        f.simulate_ram_loss()
        f.reconcile()
        before = inventory(f.root)
        f.reconcile()
        assert inventory(f.root) == before
        assert json.loads(f.receipt.read_text())['legacyLocks'] == 'cleared'
    yield 'record_once_idempotence_live_fence_then_normal_completion', 'valid', completed

    def collision(f):
        result = f.update(1)
        assert result['returncode'] == 1 and 'RECEIPT_COLLISION' in result['stderr']
        assert f.receipt.read_bytes() == b'foreign-receipt\n'
    yield 'foreign_durable_receipt_preserved', 'collision', collision

    def reboot(f):
        before = f.persistent()
        f.interrupted()
        f.simulate_ram_loss()
        f.reconcile()
        assert not f.request.exists() and not f.global_lock.exists()
        assert json.loads(f.receipt.read_text())['legacyLocks'] == 'cleared'
        assert f.persistent() == before
        assert not list((f.root / 'tmp/broray-light/run/locks').iterdir())
    yield 'interrupted_r1_and_ram_loss_reconcile_exact_persistent_locks', 'pause', reboot

    def partial(f):
        f.interrupted()
        f.global_lock.joinpath('pid').unlink()
        f.simulate_ram_loss()
        f.reconcile()
        assert not f.global_lock.exists() and not f.request.exists()
    yield 'partial_legacy_cleanup_is_recoverable_inside_recorded_inodes', 'pause', partial

    def changed(f, kind):
        f.interrupted()
        f.simulate_ram_loss()
        if kind == 'inode':
            path = f.global_lock / 'pid'
            staged = path.with_name('replacement')
            staged.write_bytes(path.read_bytes())
            staged.chmod(path.stat().st_mode & 0o777)
            staged.replace(path)
        elif kind == 'extra-child':
            (f.global_lock / 'keep').write_bytes(b'foreign\n')
        elif kind == 'receipt-mode':
            f.receipt.chmod(0o644)
        elif kind == 'symlink':
            saved = f.root / 'saved-global-lock'
            f.global_lock.rename(saved)
            f.global_lock.symlink_to(saved, target_is_directory=True)
        before = inventory(f.root / 'opt')
        f.reconcile(1, 'RECEIPT_INVALID' if kind == 'receipt-mode' else 'LEGACY_LOCK_IDENTITY')
        assert inventory(f.root / 'opt') == before, 'Refusal altered legacy state'
        assert f.request.exists()
    for kind in ('inode', 'extra-child', 'receipt-mode', 'symlink'):
        yield 'refuse_'+kind+'_without_deleting_either_lock', 'pause', lambda f, kind=kind: changed(f, kind)

    def occupied_ram(f):
        f.interrupted()
        before = inventory(f.root / 'opt')
        # No simulated reboot: old unmarked r1 work must not be adopted.
        f.reconcile(1, 'RAM_NAMESPACE')
        assert inventory(f.root / 'opt') == before
    yield 'old_unmarked_ram_work_requires_explicit_transition', 'pause', occupied_ram


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--shell', default='/bin/dash')
    parser.add_argument('--busybox', action='store_true')
    parser.add_argument('--busybox-tools', action='store_true')
    parser.add_argument('--result', type=Path)
    parser.add_argument('--callback')
    args = parser.parse_args()
    if args.callback: raise SystemExit(callback(args.callback))
    assert os.geteuid() == 0, 'Root on disposable Linux CI only'
    shell = [args.shell, 'ash'] if args.busybox else [args.shell]
    if args.busybox_tools:
        import r0013_busybox_fixture
        utility_fixture = r0013_busybox_fixture.enable()
    report = dict(stage='R0013', revision='p25-durable-transition-receipt-and-legacy-lock-recovery',
                  scope='REAL_R1_ENGINE_SIMULATED_RAM_LOSS_FIXTURE_APP_SERVICE', engineSha256=ENGINE_SHA,
                  journalSha256=hashlib.sha256(JOURNAL.read_bytes()).hexdigest(), shell=shell,
                  utilities='BusyBox applets' if args.busybox_tools else 'host utilities', tests=[])
    failed = False
    for name, mode, test in cases():
        fixture = JournalFixture(shell, mode)
        try:
            test(fixture)
            report['tests'].append(dict(name=name, status='PASS'))
        except Exception as error:
            report['tests'].append(dict(name=name, status='FAIL', error=str(error)))
            failed = True
            break
        finally:
            fixture.close()
    report['status'] = 'FAIL_FIRST_ERROR' if failed else 'PASS_LEGACY_RECEIPT_AND_RECONCILIATION'
    payload = (json.dumps(report, indent=2)+'\n').encode()
    if args.result:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_bytes(payload)
    print(payload.decode())
    if args.busybox_tools: utility_fixture.cleanup()
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
