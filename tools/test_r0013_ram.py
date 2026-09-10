#!/usr/bin/env python3
"""Root-only disposable Linux tests using real tmpfs and real processes.

This tests the shared primitive, not the still-pending integrated lifecycle.
No router, mount, network, or persistent product path is used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / 'packaging/r0013-overlay/shared/runtime-ram.sh'


class Fixture:
    def __init__(self, shell):
        self.temp = tempfile.TemporaryDirectory(prefix='r0013-ram-', dir='/dev/shm')
        self.root = Path(self.temp.name)
        self.shell = shell
        (self.root / 'tmp').mkdir(mode=0o1777)
        (self.root / 'tmp').chmod(0o1777)
        self.env = dict(os.environ, BRORAY_LIGHT_ROOT_PREFIX=str(self.root))
        self.prefix = '. "$1"; '
        self.children = []
        self.app = self.root / 'tmp/broray-light'
        self.updater = self.root / 'tmp/broray-light-updater'
        self.locks = self.app / 'run/locks'
        self.global_lock = self.locks / 'global-operation.lock'
        self.request = self.updater / 'request.lock'

    def run(self, code, expected=0):
        result = subprocess.run([*self.shell, '-c', self.prefix + code, 'fixture', str(SOURCE)],
                                env=self.env, capture_output=True, text=True, timeout=10)
        assert result.returncode == expected, (code, result.returncode, result.stdout, result.stderr)
        return result

    def prepare(self):
        self.run('brl_ram_prepare')

    def hold(self, role='global'):
        process = subprocess.Popen([*self.shell, '-c', self.prefix +
                                    'brl_lock_acquire "$2" || exit $?; echo HELD; read answer; '
                                    'brl_lock_release "$2"', 'fixture', str(SOURCE), role],
                                   env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        self.children.append(process)
        assert select.select([process.stdout], [], [], 10)[0], 'owner startup timed out'
        line = process.stdout.readline().strip()
        assert line == 'HELD', (line, process.poll(), process.stderr.read() if process.poll() is not None else '')
        return process

    def release(self, process):
        out, err = process.communicate('release\n', timeout=10)
        assert process.returncode == 0, (out, err)

    def snapshot(self, path):
        result = {}
        paths = [path] + sorted(path.rglob('*')) if path.is_dir() and not path.is_symlink() else [path]
        for item in paths:
            st = item.lstat()
            content = os.readlink(item) if item.is_symlink() else item.read_bytes().hex() if item.is_file() else None
            result[str(item.relative_to(self.root))] = (st.st_ino, st.st_mode, st.st_uid, content)
        return result

    def close(self):
        for process in self.children:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=10)
        self.temp.cleanup()


def cases():
    def clean(f):
        f.run('brl_ram_prepare; brl_lock_acquire global && brl_lock_release global')
        assert not f.global_lock.exists()
        assert not (f.root / 'opt').exists(), 'RAM primitive wrote below /opt'
        assert not list(f.locks.glob('.claim.*')) and not (f.locks / 'admission').exists()
        assert (f.app / 'run/web-new/sessions').stat().st_mode & 0o777 == 0o700
    yield 'clean_real_tmpfs_and_no_persistent_write', clean

    def repeat(f):
        f.prepare()
        before = f.snapshot(f.app)
        f.prepare()
        assert f.snapshot(f.app) == before
    yield 'namespace_idempotence', repeat

    def unsafe_namespace(f, kind):
        if kind == 'symlink':
            target = f.root / 'foreign'
            target.mkdir()
            (target / 'keep').write_bytes(b'foreign')
            f.app.symlink_to(target, target_is_directory=True)
        else:
            f.app.mkdir(mode=0o700)
            (f.app / 'owner').write_text('foreign\n')
            (f.app / 'owner').chmod(0o600)
        before = f.snapshot(f.root)
        f.run('brl_ram_prepare', 3)
        assert f.snapshot(f.root) == before
    for kind in ('symlink', 'unowned'):
        yield 'refuse_' + kind + '_namespace_without_mutation', lambda f, kind=kind: unsafe_namespace(f, kind)

    def bad_mode(f):
        f.prepare()
        f.app.chmod(0o755)
        before = f.snapshot(f.app)
        f.run('brl_ram_prepare', 3)
        assert f.snapshot(f.app) == before
    yield 'refuse_wrong_mode_without_repair', bad_mode

    def non_ram(f):
        with tempfile.TemporaryDirectory(prefix='r0013-nonram-', dir='/var/tmp') as tmp:
            root = Path(tmp)
            (root / 'tmp').mkdir(mode=0o1777)
            (root / 'tmp').chmod(0o1777)
            f.env['BRORAY_LIGHT_ROOT_PREFIX'] = tmp
            f.run('brl_ram_prepare', 3)
            assert list((root / 'tmp').iterdir()) == []
    yield 'refuse_non_tmpfs_before_namespace_creation', non_ram

    def live_owner(f):
        f.prepare()
        owner = f.hold()
        before = f.snapshot(f.global_lock)
        f.run('brl_lock_acquire global', 2)
        f.run('brl_lock_release global', 3)
        assert f.snapshot(f.global_lock) == before
        f.release(owner)
        f.run('brl_lock_acquire global && brl_lock_release global')
    yield 'live_owner_blocks_second_owner_and_foreign_release', live_owner

    def dead_owner(f):
        f.prepare()
        owner = f.hold()
        owner.kill()
        owner.communicate(timeout=10)
        f.run('brl_lock_acquire global && brl_lock_release global')
    yield 'dead_owner_reclaimed_with_serialized_admission', dead_owner

    def reused_pid(f):
        f.prepare()
        f.global_lock.mkdir(mode=0o700)
        (f.global_lock / 'owner').write_text(f'BROray-Light:lock/1 {os.getpid()} 0\n')
        (f.global_lock / 'owner').chmod(0o600)
        f.run('brl_lock_acquire global && brl_lock_release global')
    yield 'reused_pid_starttime_does_not_block', reused_pid

    def legacy(f, role):
        f.prepare()
        relative = 'opt/var/lock/broray-light/global-operation.lock' if role == 'global' else 'opt/var/lock/broray-light-updater/request.lock'
        path = f.root / relative
        path.parent.mkdir(parents=True)
        path.symlink_to('absent')
        before = f.snapshot(f.root / 'opt')
        f.run('brl_lock_acquire global', 2)
        f.run('brl_lock_acquire request', 2)
        assert f.snapshot(f.root / 'opt') == before
    for role in ('global', 'request'):
        yield 'legacy_' + role + '_fence_is_read_only', lambda f, role=role: legacy(f, role)

    def request_admission(f):
        f.prepare()
        owner = f.hold('request')
        f.run('brl_lock_acquire global', 2)
        f.run('brl_lock_acquire request', 2)
        f.run('brl_lock_acquire updater-global', 3)
        f.release(owner)
        f.run('brl_lock_acquire request && brl_lock_acquire updater-global && '
              'brl_lock_release updater-global && brl_lock_release request')
    yield 'updater_request_and_application_share_admission', request_admission

    def global_blocks_updater(f):
        f.prepare()
        owner = f.hold()
        f.run('brl_lock_acquire request && brl_lock_acquire updater-global; rc=$?; '
              'brl_lock_release request || exit 91; exit "$rc"', 2)
        f.release(owner)
    yield 'application_global_owner_blocks_updater', global_blocks_updater

    def unsafe_lock(f, kind):
        f.prepare()
        if kind == 'symlink':
            f.global_lock.symlink_to(f.root / 'foreign')
        else:
            f.global_lock.mkdir(mode=0o700)
            (f.global_lock / 'owner').write_text('BROray-Light:lock/1 99999999 1\n' if kind == 'unexpected-child' else 'garbage\n')
            (f.global_lock / 'owner').chmod(0o600)
            if kind == 'unexpected-child':
                (f.global_lock / 'keep').write_bytes(b'foreign')
        before = f.snapshot(f.global_lock)
        f.run('brl_lock_acquire global', 3)
        assert f.snapshot(f.global_lock) == before
    for kind in ('symlink', 'malformed', 'unexpected-child'):
        yield 'refuse_' + kind + '_lock_without_cleanup', lambda f, kind=kind: unsafe_lock(f, kind)

    def admission_collision(f, directory):
        f.prepare()
        path = f.locks / 'admission'
        if directory:
            path.mkdir(mode=0o700)
        else:
            path.write_text('BROray-Light:lock/1 99999999 1\n')
            path.chmod(0o600)
        before = f.snapshot(path)
        f.run('brl_lock_acquire global', 2)
        assert f.snapshot(path) == before
        assert not list(f.locks.glob('.claim.*'))
    yield 'abandoned_admission_requires_explicit_recovery', lambda f: admission_collision(f, False)
    yield 'admission_directory_collision_no_nested_claim', lambda f: admission_collision(f, True)

    def concurrency(f):
        f.prepare()
        processes = [subprocess.Popen([*f.shell, '-c', f.prefix +
                                      'brl_lock_acquire global || exit $?; echo HELD; read answer; '
                                      'brl_lock_release global', 'fixture', str(SOURCE)], env=f.env,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True) for _ in range(12)]
        f.children.extend(processes)
        winners = []
        for process in processes:
            assert select.select([process.stdout], [], [], 10)[0]
            if process.stdout.readline().strip() == 'HELD':
                winners.append(process)
            else:
                process.wait(timeout=10)
                assert process.returncode == 2, process.stderr.read()
        assert len(winners) == 1, len(winners)
        f.release(winners[0])
        assert not list(f.locks.iterdir()), 'lock or admission leak'
    yield 'twelve_concurrent_contenders_exactly_one_owner', concurrency


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--shell', default='/bin/dash')
    parser.add_argument('--busybox', action='store_true')
    parser.add_argument('--busybox-tools', action='store_true')
    parser.add_argument('--result', type=Path)
    args = parser.parse_args()
    assert os.geteuid() == 0, 'Run only as root in disposable Linux CI'
    shell = [args.shell, 'ash'] if args.busybox else [args.shell]
    if args.busybox_tools:
        import r0013_busybox_fixture
        utility_fixture = r0013_busybox_fixture.enable()
    report = dict(stage='R0013', revision='p21-native-busybox-utility-acceptance', status='IN_PROGRESS',
                  utilities='BusyBox applets' if args.busybox_tools else 'host utilities',
                  scope='REAL_TMPFS_AND_PROCESSES_NO_LIFECYCLE_OR_ROUTER', shell=shell,
                  sourceSha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(), tests=[])
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
    report['status'] = 'FAIL_FIRST_ERROR' if failed else 'PASS_BOUNDED_PRIMITIVE'
    payload = (json.dumps(report, indent=2) + '\n').encode()
    if args.result:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_bytes(payload)
    print(payload.decode())
    if args.busybox_tools:
        utility_fixture.cleanup()
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
