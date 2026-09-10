#!/usr/bin/env python3
"""Real runtime file replacement/restore; scoped process/fence boundary mocked."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[1]
APP = REPO / 'packaging/r0013-overlay/app'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--shell', default='/bin/dash')
    parser.add_argument('--busybox', action='store_true')
    parser.add_argument('--busybox-tools', action='store_true')
    parser.add_argument('--result', type=Path)
    args = parser.parse_args()
    assert os.geteuid() == 0, 'Disposable Linux CI root only'
    shell = [args.shell, 'ash'] if args.busybox else [args.shell]
    if args.busybox_tools:
        import r0013_busybox_fixture
        utility_fixture = r0013_busybox_fixture.enable()
    records = []
    failed = False
    modes = ['missing-backup', 'wrong-backup-path', 'backup-symlink', 'backup-sha-mismatch',
             'stop-refused', 'foreign-current', 'foreign-new', 'runtime-parent-symlink',
             'no-active-transaction', 'valid-stopped', 'valid-running', 'partial-owned-new',
             'current-absent', 'restart-failed', 'dispatch-rollback-before-release',
             'dispatch-recovery-failure-preserves-fence']
    for mode in modes:
        try:
            with tempfile.TemporaryDirectory(prefix='r0013-xray-rollback-') as temporary:
                root = Path(temporary)
                (root / 'lib').mkdir()
                (root / 'runtime').mkdir(mode=0o700)
                for name in ('xray-update.sh', 'xray-releases.sh'):
                    (root / 'lib' / name).write_bytes((APP / 'lib' / name).read_bytes())
                (root / 'lib/operation-lock.sh').write_text('''broray_operation_lock_acquire() {
 printf 'acquire\n' >> "$TEST_EVENTS"; printf held > "$TEST_FENCE";
}
broray_operation_lock_release() {
 printf 'fence-release\n' >> "$TEST_EVENTS"; rm "$TEST_FENCE";
}
''')
                runtime = root / 'runtime/xray'
                backup = runtime.with_name('xray.broray-light-backup')
                staged = runtime.with_name('xray.new')
                runtime.write_bytes(b'candidate-runtime\n')
                backup.write_bytes(b'previous-good-runtime\n')
                runtime.chmod(0o755)
                backup.chmod(0o755)
                st = runtime.stat()
                stage_id = f'{st.st_dev}:{st.st_ino}'
                events = root / 'events'
                events.write_text('')
                env = dict(os.environ, BRORAY_BASE=str(root), BRORAY_XRAY_BINARY=str(runtime),
                           TEST_OLD_SHA=hashlib.sha256(backup.read_bytes()).hexdigest(), TEST_STAGE_ID=stage_id,
                           TEST_EVENTS=str(events), TEST_FENCE=str(root / 'fence'), TEST_BACKUP=str(backup),
                           TEST_STOP_RC='0', TEST_START_RC='0', TEST_WAS_RUNNING='false', TEST_ACTIVE='true',
                           TEST_REQUIRE_FENCE='false')
                if mode in ('missing-backup', 'dispatch-recovery-failure-preserves-fence'): backup.unlink()
                elif mode == 'wrong-backup-path': env['TEST_BACKUP'] = str(root / 'missing')
                elif mode == 'backup-symlink':
                    saved = root / 'real-backup'
                    backup.rename(saved)
                    backup.symlink_to(saved)
                elif mode == 'backup-sha-mismatch': backup.write_bytes(b'foreign-backup\n')
                elif mode == 'stop-refused': env['TEST_STOP_RC'] = '1'
                elif mode == 'foreign-current': env['TEST_STAGE_ID'] = '0:1'
                elif mode == 'foreign-new': staged.write_bytes(b'foreign-preserve\n')
                elif mode == 'runtime-parent-symlink':
                    parent = root / 'runtime'
                    real = root / 'actual-runtime'
                    parent.rename(real)
                    parent.symlink_to(real, target_is_directory=True)
                elif mode == 'no-active-transaction': env['TEST_ACTIVE'] = 'false'
                elif mode in ('valid-running', 'restart-failed'): env['TEST_WAS_RUNNING'] = 'true'
                elif mode == 'partial-owned-new':
                    runtime.rename(staged)
                    staged.write_bytes(b'partial-write\n')
                    staged.chmod(0o600)
                elif mode == 'current-absent': runtime.unlink()
                if mode == 'restart-failed': env['TEST_START_RC'] = '1'
                before = {str(p): (p.read_bytes() if p.is_file() else None) for p in (runtime, backup, staged)}
                code = '''. "$BRORAY_BASE/lib/xray-update.sh"
broray_xray_old_sha256="$TEST_OLD_SHA"
broray_xray_stage_id="$TEST_STAGE_ID"
broray_xray_old_backup="$TEST_BACKUP"
broray_xray_was_running="$TEST_WAS_RUNNING"
BRORAY_XRAY_REPLACEMENT_ACTIVE="$TEST_ACTIVE"
broray_xray_stop() {
 [ "$TEST_REQUIRE_FENCE" != true ] || [ -f "$TEST_FENCE" ] || return 1
 printf 'stop\n' >> "$TEST_EVENTS"; return "$TEST_STOP_RC"
}
broray_xray_is_running() { return 1; }
broray_xray_start() { printf 'start\n' >> "$TEST_EVENTS"; return "$TEST_START_RC"; }
broray_xray_wait_running() { printf 'wait\n' >> "$TEST_EVENTS"; return 0; }
broray_xray_update_work_clean() { printf 'work-clean\n' >> "$TEST_EVENTS"; }
broray_xray_update_lock_release() { printf 'xray-lock-release\n' >> "$TEST_EVENTS"; }
'''
                if mode.startswith('dispatch-'):
                    env['TEST_REQUIRE_FENCE'] = 'true'
                    code += '''broray_xray_update_install() {
 trap 'broray_xray_update_abort_cleanup' 0
 return 7
}
broray_xray_install_dispatch update
'''
                else:
                    code += 'broray_xray_update_restore_binary "$TEST_BACKUP" "$TEST_WAS_RUNNING"\n'
                result = subprocess.run([*shell, '-c', code], env=env, capture_output=True, text=True, timeout=15)
                after = {str(p): (p.read_bytes() if p.is_file() else None) for p in (runtime, backup, staged)}
                event_list = events.read_text().splitlines()
                successful_restore = mode in ('valid-stopped', 'valid-running', 'partial-owned-new', 'current-absent', 'restart-failed', 'dispatch-rollback-before-release')
                if successful_restore:
                    expected = 7 if mode.startswith('dispatch-') else 1 if mode == 'restart-failed' else 0
                    assert result.returncode == expected, (result.returncode, result.stdout, result.stderr)
                    assert runtime.read_bytes() == b'previous-good-runtime\n' and not backup.exists() and not staged.exists()
                    if mode == 'dispatch-rollback-before-release':
                        assert event_list == ['acquire', 'stop', 'work-clean', 'xray-lock-release', 'fence-release'], event_list
                        assert not (root / 'fence').exists()
                    elif mode == 'valid-running': assert event_list == ['stop', 'start', 'wait'], event_list
                else:
                    assert result.returncode != 0 and after == before, (mode, result.returncode, before, after, result.stderr)
                    if mode == 'dispatch-recovery-failure-preserves-fence':
                        assert event_list == ['acquire'] and (root / 'fence').exists(), event_list
                        assert 'XRAY_RECOVERY_REQUIRED' in result.stderr
                    elif mode == 'stop-refused': assert event_list == ['stop'], event_list
                    else: assert event_list == [], event_list
                records.append(dict(name=mode, status='PASS'))
        except Exception as error:
            records.append(dict(name=mode, status='FAIL', error=str(error)))
            failed = True
            break
    report = dict(stage='R0013', revision='p32-xray-validated-rollback-before-fence-release',
                  status='FAIL_FIRST_ERROR' if failed else 'PASS_SCOPED_XRAY_ROLLBACK', shell=shell,
                  scope='Actual replacement/restore bytes; process and global-lock calls mocked for ordering only',
                  utilities='BusyBox applets' if args.busybox_tools else 'host utilities',
                  sourceSha256={name:hashlib.sha256((APP / 'lib' / name).read_bytes()).hexdigest() for name in ('xray-update.sh','xray-releases.sh')}, tests=records)
    payload = (json.dumps(report, indent=2)+'\n').encode()
    if args.result:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_bytes(payload)
    print(payload.decode())
    if args.busybox_tools: utility_fixture.cleanup()
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
