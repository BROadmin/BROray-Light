#!/usr/bin/env python3
"""Compiled application path contract, actual RAM guard and lock adapter."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from build_r0013_release import prepared_app
from r0013_inputs import app_inputs
from r0013_runtime_paths import compile_runtime, GUARD, ROOT
from test_r0013_r1_admission import inventory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--shell', default='/bin/dash')
    parser.add_argument('--busybox', action='store_true')
    parser.add_argument('--busybox-tools', action='store_true')
    parser.add_argument('--result', type=Path)
    args = parser.parse_args()
    assert os.geteuid() == 0
    shell = [args.shell, 'ash'] if args.busybox else [args.shell]
    if args.busybox_tools:
        import r0013_busybox_fixture
        utility_fixture = r0013_busybox_fixture.enable()
    records = []
    failed = False
    try:
        raw = app_inputs()
        app = prepared_app()
        manifest = json.loads(app['share/lifecycle/RUNTIME-PATH-MANIFEST.json'][0])
        assert len(manifest['files']) == 41
        for row in manifest['files']:
            data, mode = app[row['path']]
            # Web cache-token stamping occurs after the path compiler.
            compiled = compile_runtime(raw)[row['path']][0]
            assert hashlib.sha256(compiled).hexdigest() == row['sha256']
            if row['guard']: assert GUARD in data
        for name in ('bin/xray', 'bin/broray-system', 'lib/xray-process.sh'):
            assert app[name] == raw[name], name
        for name, (data, mode) in app.items():
            if name.startswith(('bin/', 'lib/', 'web-new/api/')):
                assert b'/tmp/broray-light/runtime' not in data and b'$BRL_RAM/runtime' not in data, name
        records.append(dict(name='exact_41_file_manifest_and_durable_xray_references', status='PASS'))
        changed = dict(raw)
        changed['lib/web-auth.sh'] = (raw['lib/web-auth.sh'][0]+b'\n# changed\n', raw['lib/web-auth.sh'][1])
        try:
            compile_runtime(changed)
            raise RuntimeError('Modified input silently accepted')
        except AssertionError as error:
            assert 'runtime transform input changed' in str(error)
        records.append(dict(name='changed_native_auth_input_refused_before_transformation', status='PASS'))
        for name, (data, mode) in app.items():
            if name.startswith(('bin/', 'lib/', 'web-new/api/')) and (name.startswith('bin/') or name.endswith(('.sh','.cgi'))):
                checked = subprocess.run([*shell, '-n'], input=data, capture_output=True, timeout=10)
                assert checked.returncode == 0, (name, checked.stderr.decode())
        records.append(dict(name='every_compiled_shell_entrypoint_syntax', status='PASS'))
        for case in ('fresh', 'overrides', 'removed-installer-tmpdir', 'foreign-namespace', 'foreign-root', 'helper-symlink', 'coownership', 'legacy-fence', 'global-lock'):
            with tempfile.TemporaryDirectory(prefix='r0013-runtime-paths-', dir='/dev/shm') as temporary:
                root = Path(temporary)
                (root / 'tmp').mkdir(mode=0o1777)
                (root / 'tmp').chmod(0o1777)
                library = root / 'opt/broray-light/lib'
                library.mkdir(parents=True)
                for name in ('runtime-ram.sh', 'runtime-environment.sh', 'operation-lock.sh'):
                    (library / name).write_bytes(app['lib/'+name][0])
                env = dict(os.environ, BRORAY_LIGHT_ROOT_PREFIX=str(root))
                if case == 'foreign-namespace':
                    foreign = root / 'tmp/broray-light'
                    foreign.mkdir(mode=0o700)
                    foreign.joinpath('unknown').write_bytes(b'preserve\n')
                elif case == 'foreign-root': env['BRORAY_ROOT'] = '/opt/broray'
                elif case == 'coownership': (root / 'opt/broray').symlink_to('missing')
                elif case == 'helper-symlink':
                    path = library / 'runtime-ram.sh'
                    saved = library / 'saved-helper'
                    path.rename(saved)
                    path.symlink_to(saved)
                elif case == 'removed-installer-tmpdir':
                    env['TMPDIR'] = str(root / 'tmp/broray-light-install.removed/opkg')
                elif case == 'overrides':
                    env['TMPDIR'] = '/opt/foreign-scratch'
                    for name in ('BRORAY_XRAY_UPDATE_TMP_ROOT','BRORAY_XRAY_RELEASE_CACHE','BRORAY_XRAY_DOWNLOAD_ROOT',
                                 'BRORAY_XRAY_UPDATE_WORK','BRORAY_NATIVE_AUTH_DIR','BRORAY_NATIVE_AUTH_RUNTIME',
                                 'BRORAY_NATIVE_AUTH_CONFIG','BRORAY_NATIVE_AUTH_PIDFILE','BRORAY_NATIVE_AUTH_LOG',
                                 'BRORAY_SUB_RUN','BRORAY_SUB_LOG','BRORAY_CHECK_STATE','BRORAY_INTERFACE_LAST_EVIDENCE',
                                 'BRORAY_INTERFACE_FAILURE_EVIDENCE','BRORAY_KEENETIC_STATUS_FILE','BRORAY_XRAY_STATUS_CACHE_FILE'):
                        env[name] = '/opt/foreign-scratch'
                elif case == 'legacy-fence':
                    (root / 'opt/var/lock/broray-light-updater/request.lock').mkdir(parents=True)
                before = inventory(root)
                command = '. "$1" || exit 1\n'
                command += '''[ "$TMPDIR" = "$BRL_RAM/tmp" ] || exit 91
probe=$(mktemp "$TMPDIR/runtime-probe.XXXXXX") || exit 92
test -f "$probe" && rm "$probe" || exit 93
'''
                if case in ('legacy-fence', 'global-lock'):
                    command += '. "$2" || exit 1; broray_operation_lock_acquire fixture || exit $?; broray_operation_lock_release\n'
                else:
                    command += '''printf '%s\n' "$BRL_RAM" "$BRORAY_XRAY_UPDATE_TMP_ROOT" "$BRORAY_XRAY_RELEASE_CACHE" "$BRORAY_XRAY_DOWNLOAD_ROOT" "$BRORAY_XRAY_UPDATE_WORK" "$BRORAY_NATIVE_AUTH_DIR" "$BRORAY_NATIVE_AUTH_RUNTIME" "$BRORAY_NATIVE_AUTH_CONFIG" "$BRORAY_NATIVE_AUTH_PIDFILE" "$BRORAY_NATIVE_AUTH_LOG" "$BRORAY_SUB_RUN" "$BRORAY_SUB_LOG" "$BRORAY_CHECK_STATE" "$BRORAY_INTERFACE_LAST_EVIDENCE" "$BRORAY_INTERFACE_FAILURE_EVIDENCE" "$BRORAY_KEENETIC_STATUS_FILE" "$BRORAY_XRAY_STATUS_CACHE_FILE"
'''
                result = subprocess.run([*shell, '-c', command, 'fixture', str(library / 'runtime-environment.sh'), str(library / 'operation-lock.sh')],
                                        env=env, capture_output=True, text=True, timeout=15)
                if case in ('foreign-namespace','foreign-root','helper-symlink','coownership'):
                    assert result.returncode == 1 and inventory(root) == before, (case,result.stderr)
                elif case == 'legacy-fence':
                    assert result.returncode == 2, (result.returncode,result.stderr)
                    assert (root / 'opt/var/lock/broray-light-updater/request.lock').exists()
                    assert not (root / 'tmp/broray-light/run/locks/global-operation.lock').exists()
                else:
                    assert result.returncode == 0, (case,result.returncode,result.stderr)
                    if case != 'global-lock':
                        values = result.stdout.splitlines()
                        assert len(values) == 17 and all(value == str(root / 'tmp/broray-light') or value.startswith(str(root / 'tmp/broray-light')+'/') for value in values), values
                    assert not (root / 'opt/var').exists(), 'Application runtime created persistent operation state'
                    assert not list((root / 'tmp/broray-light/run/locks').iterdir())
                records.append(dict(name='runtime_guard_'+case, status='PASS'))
    except Exception as error:
        records.append(dict(name='first_error', status='FAIL', error=str(error)))
        failed = True
    report = dict(stage='R0013', revision='p34-component-bounded-application-ram-path-contract',
                  status='FAIL_FIRST_ERROR' if failed else 'PASS_COMPILED_PATHS_GUARD_AND_LOCK_ADAPTER',
                  scope='Compiled shell syntax, path manifest, actual tmpfs environment guard/lock adapter; NOT full startup or old-data migration',
                  specificationSha256=hashlib.sha256((ROOT / 'runtime-paths.json').read_bytes()).hexdigest(),
                  shell=shell, utilities='BusyBox applets' if args.busybox_tools else 'host utilities', tests=records)
    payload = (json.dumps(report, indent=2)+'\n').encode()
    if args.result:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_bytes(payload)
    print(payload.decode())
    if args.busybox_tools: utility_fixture.cleanup()
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
