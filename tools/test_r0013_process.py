#!/usr/bin/env python3
"""Fail-fast Xray identity tests. Fixture results are not target-runtime proof."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def shell_path(path: Path) -> str:
    value = path.resolve().as_posix()
    return '/' + value[0].lower() + value[2:] if os.name == 'nt' else value


def run(shell: str, command: str, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run([shell, '-c', command], env=env, capture_output=True, text=True, timeout=20)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--shell', default=shutil.which('dash') or shutil.which('sh'))
    parser.add_argument('--live-linux', action='store_true')
    args = parser.parse_args()
    if not args.shell:
        raise SystemExit('POSIX shell unavailable')
    repo = Path(__file__).resolve().parents[1]
    app = repo / 'packaging/r0013-overlay/app'
    source = app / 'lib/xray-process.sh'
    records = []
    for path in sorted(app.rglob('*')):
        if path.is_file() and (path.suffix == '.sh' or path.parent.name == 'bin'):
            result = subprocess.run([args.shell, '-n', str(path)], capture_output=True, text=True)
            assert result.returncode == 0, (str(path), result.stderr)
            records.append({'test': 'syntax:' + path.relative_to(app).as_posix(), 'status': 'PASS'})

    with tempfile.TemporaryDirectory(prefix='r0013-process-') as temporary:
        root = Path(temporary)
        proc = root / 'proc'
        proc.mkdir()
        fixture = root / 'identity.sh'
        # Only the test copy redirects /proc; production has no proc-root override.
        fixture.write_text(source.read_text('utf-8').replace('/proc/', shell_path(proc) + '/'), encoding='utf-8', newline='\n')
        binary_dir = root / 'bin'
        binary_dir.mkdir()
        pidof = binary_dir / 'pidof'
        pidof.write_text('#!/bin/sh\nprintf "%s\\n" "$FIXTURE_PIDS"\n', encoding='utf-8', newline='\n')
        pidof.chmod(0o755)
        env = dict(os.environ, BRORAY_XRAY_BINARY='/managed/xray', BRORAY_XRAY_CONFIG='/managed/config.json')
        env['PATH'] = str(binary_dir) + os.pathsep + str(Path(args.shell).parent) + os.pathsep + env.get('PATH', '')
        env['SIGNAL_LOG'] = shell_path(root / 'signals')
        prologue = '''
readlink() {
    if [ "$1" = '-f' ]; then printf '%s\n' "$2"; else cat "$1"; fi
}
kill() {
    [ "$1" != '-0' ] || return 0
    printf '%s %s\n' "$1" "$2" >>"$SIGNAL_LOG"
}
'''+'. "' + shell_path(fixture) + '"\n'

        def put(pid: int, argv: list[str], exe: str = '/managed/xray', state: str = 'S') -> None:
            directory = proc / str(pid)
            directory.mkdir(exist_ok=True)
            (directory / 'exe').write_text(exe, encoding='utf-8')
            (directory / 'stat').write_text(f'{pid} (xray) ' + ' '.join([state] + ['0'] * 18 + ['123456'] + ['0'] * 5), encoding='utf-8')
            (directory / 'cmdline').write_bytes(b'\0'.join(s.encode() for s in argv) + b'\0')

        cases = [
            ('owned-short-config', ['xray', 'run', '-c', '/managed/config.json'], True),
            ('owned-long-config', ['xray', 'run', '--config=/managed/config.json'], True),
            ('owned-config', ['xray', 'run', '-config', '/managed/config.json'], True),
            ('validator-before-config', ['xray', 'run', '-test', '-c', '/managed/config.json'], False),
            ('validator-after-config', ['xray', 'run', '-c', '/managed/config.json', '-test'], False),
            ('validator-equals', ['xray', 'run', '-c', '/managed/config.json', '--test=true'], False),
            ('foreign-config', ['xray', 'run', '-c', '/opt/broray/config/config.json'], False),
            ('config-prefix', ['xray', 'run', '-c', '/managed/config.json.backup'], False),
            ('missing-config', ['xray', 'run'], False),
            ('missing-value', ['xray', 'run', '-c'], False),
            ('duplicate-config', ['xray', 'run', '-c', '/managed/config.json', '-c', '/managed/config.json'], False),
            ('config-directory', ['xray', 'run', '-c', '/managed/config.json', '-confdir', '/managed'], False),
            ('version-command', ['xray', 'version', '-c', '/managed/config.json'], False),
        ]
        for name, argv, accepted in cases:
            put(101, argv)
            result = run(args.shell, prologue + 'broray_xray_runtime_identity 101', env)
            assert (result.returncode == 0) == accepted, (name, result.returncode, result.stdout, result.stderr)
            if accepted:
                assert result.stdout.strip() == '123456', (name, result.stdout)
            records.append({'test': name, 'status': 'PASS'})
        runtime_argv = ['xray', 'run', '-c', '/managed/config.json']
        for name, exe, state in [('foreign-executable', '/opt/broray/runtime/xray', 'S'), ('executable-prefix', '/managed/xray.old', 'S'), ('zombie', '/managed/xray', 'Z')]:
            put(101, runtime_argv, exe, state)
            assert run(args.shell, prologue + 'broray_xray_runtime_identity 101', env).returncode != 0, name
            records.append({'test': name, 'status': 'PASS'})
        for pid in ['0', '1', 'abc', '10/1', '999']:
            assert run(args.shell, prologue + f'broray_xray_runtime_identity "{pid}"', env).returncode != 0, pid
            records.append({'test': 'reject-pid:' + pid, 'status': 'PASS'})
        put(101, runtime_argv)
        put(102, ['xray', 'run', '-test', '-c', '/managed/config.json'])
        put(103, runtime_argv, '/opt/broray/runtime/xray')
        env['FIXTURE_PIDS'] = '102 103 101'
        result = run(args.shell, prologue + 'broray_xray_runtime_pid', env)
        assert result.returncode == 0 and result.stdout.strip() == '101', ('validator-first', result)
        records.append({'test': 'validator-and-foreign-before-runtime', 'status': 'PASS'})
        result = run(args.shell, prologue + 'broray_xray_runtime_signal TERM', env)
        assert result.returncode == 0 and (root / 'signals').read_text().strip() == '-TERM 101', ('scoped-signal', result)
        records.append({'test': 'signal-only-managed-runtime', 'status': 'PASS'})
        assert run(args.shell, prologue + 'broray_xray_runtime_signal KILLALL', env).returncode != 0
        records.append({'test': 'reject-unlisted-signal', 'status': 'PASS'})

        # Init errors must not be converted to success merely because another
        # status poll looks healthy; this tests the real control library.
        libenv = dict(env, BRORAY_ROOT=shell_path(app), BRORAY_XRAY_INIT='/bin/false')
        for action in ['start', 'stop', 'restart']:
            command = '. "' + shell_path(app / 'lib/xray-control.sh') + '"\n' + '''
broray_xray_validate() { return 0; }
broray_xray_wait_running() { return 0; }
broray_xray_wait_stopped() { return 0; }
broray_xray_action_result() { printf '%s %s\n' "$1" "$2"; }
''' + 'broray_xray_' + action
            result = run(args.shell, command, libenv)
            assert result.returncode != 0 and result.stdout.strip() == action + ' false', ('init-error-' + action, result)
            records.append({'test': 'init-error-propagation:' + action, 'status': 'PASS'})

        if args.live_linux:
            assert os.name == 'posix' and Path('/proc/self/exe').exists(), 'live-linux requires Linux /proc'
            c_file = root / 'xray.c'
            c_file.write_text('#include <unistd.h>\nint main(void) { for (;;) pause(); }\n')
            owned, foreign = root / 'owned/xray', root / 'foreign/xray'
            owned.parent.mkdir()
            foreign.parent.mkdir()
            subprocess.run(['cc', str(c_file), '-o', str(owned)], check=True, capture_output=True)
            shutil.copy2(owned, foreign)
            runtime_env = dict(os.environ, BRORAY_XRAY_BINARY=str(owned), BRORAY_XRAY_CONFIG=str(root / 'config.json'))
            config = runtime_env['BRORAY_XRAY_CONFIG']
            processes = [subprocess.Popen([str(owned), 'run', '-c', config]),
                         subprocess.Popen([str(owned), 'run', '-test', '-c', config]),
                         subprocess.Popen([str(foreign), 'run', '-c', config])]
            try:
                live = '. "' + str(source) + '"\n'
                result = run(args.shell, live + 'broray_xray_runtime_pid', runtime_env)
                assert result.returncode == 0 and result.stdout.strip() == str(processes[0].pid), ('live-identity', result)
                result = run(args.shell, live + 'broray_xray_runtime_signal TERM', runtime_env)
                assert result.returncode == 0, ('live-signal', result)
                processes[0].wait(timeout=5)
                assert processes[1].poll() is None and processes[2].poll() is None, 'foreign process signalled'
                records.append({'test': 'live-linux-exe-argv-and-scoped-signal', 'status': 'PASS'})
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.terminate()
                    process.wait(timeout=5)

    print(json.dumps({'schemaVersion': 1, 'stage': 'R0013', 'revision': 'p4-process-equals-config-guard',
        'status': 'PASS', 'liveLinux': args.live_linux, 'targetRouterTested': False,
        'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'tests': records}, indent=2))


if __name__ == '__main__':
    main()
