#!/usr/bin/env python3
"""Real r1 engine + signed fixture slot containing real external platform bytes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import r0013_platform
from build_r0013_release import primitives
from test_r0013_r1_admission import R1Fixture, RAM, ADMISSION, inventory, ENGINE_SHA
from test_r0013_updater_ram import NEW, OLD

HELPERS = [RAM, ADMISSION, ADMISSION.with_name('lifecycle-r1-journal.sh'),
           ADMISSION.with_name('lifecycle-r1-ram.sh'), ADMISSION.with_name('lifecycle-r1-platform.sh')]
PLATFORM = HELPERS[-1]


def call(shell, env, action):
    code = '; '.join('. "$'+str(i)+'"' for i in range(1, 6))+'; '+action
    return subprocess.run([*shell, '-c', code, 'fixture', *map(str, HELPERS)], env=env,
                          capture_output=True, text=True, timeout=45)


def callback(mode):
    root = Path(os.environ['BRORAY_LIGHT_ROOT_PREFIX'])
    shell = json.loads(os.environ['R0013_FIXTURE_SHELL'])
    receipt = root / 'opt/var/lib/broray-light-updater/legacy-transition.json'
    payload_dir = root / 'opt/broray-light/releases' / NEW / 'app/share/lifecycle/platform'
    manifest = json.loads((payload_dir / 'manifest.json').read_text())
    before = {row['path']: (root / row['path']).read_bytes() if (root / row['path']).exists() else None for row in manifest['files']}
    recorded = call(shell, os.environ, 'brl_r1_ram_promote')
    assert recorded.returncode == 0, recorded.stderr
    restore_fault = None
    if mode == 'foreign-target':
        path = root / manifest['files'][0]['path']
        content = path.read_bytes()
        path.write_bytes(b'foreign\n')
        restore_fault = lambda: path.write_bytes(content)
    elif mode == 'symlink-parent':
        path = root / 'opt/libexec/broray-light-web-publish'
        saved = root / 'fixture-saved-publisher'
        path.rename(saved)
        path.symlink_to(saved, target_is_directory=True)
        def restore_fault():
            path.unlink()
            saved.rename(path)
    elif mode == 'tampered-payload':
        path = payload_dir / 'new' / manifest['files'][0]['path']
        content = path.read_bytes()
        path.write_bytes(b'tampered\n')
        restore_fault = lambda: path.write_bytes(content)
    baseline = inventory(root)
    if restore_fault:
        failed = call(shell, os.environ, 'brl_platform_activate')
        assert failed.returncode == 1 and inventory(root) == baseline, (failed.returncode, failed.stderr)
        restore_fault()
        restored = call(shell, os.environ, 'brl_r1_ram_restore')
        assert restored.returncode == 0, restored.stderr
        report = dict(returncode=1, stderr=failed.stderr, phase='refused-before-platform-write')
    else:
        if mode.startswith('partial-'):
            # Build a precisely journaled interrupted transaction using the
            # actual platform copy operation, then resume/rollback in a new shell.
            index = int(mode.split('-')[1])
            action = '''brl_platform_payload && brl_platform_targets_valid old &&
brl_r1_ram_save --arg sha "$BRL_PLATFORM_SHA" '.platform={phase:"prepared",manifestSha256:$sha}' &&
brl_platform_replace '''+shlex.quote(manifest['files'][index]['path'])+' new'
            partial = call(shell, os.environ, action)
            assert partial.returncode == 0, partial.stderr
        elif mode.startswith('staged-'):
            index = int(mode.split('-')[1])
            setup = call(shell, os.environ, '''brl_platform_payload && brl_platform_targets_valid old &&
brl_r1_ram_save --arg sha "$BRL_PLATFORM_SHA" '.platform={phase:"prepared",manifestSha256:$sha}' ''')
            assert setup.returncode == 0, setup.stderr
            row = manifest['files'][index]
            target = root / row['path']
            staged = target.with_name('.'+target.name+'.r0013-installed')
            staged.write_bytes(b'partial owned candidate\n')
            staged.chmod(0o600)
            data = json.loads(receipt.read_text())
            st = staged.stat()
            data['platform']['staged'] = {row['path']: dict(inode=f'{st.st_dev}:{st.st_ino}', sha256=row['newSha256'])}
            receipt.write_text(json.dumps(data))
        if mode.endswith('-rollback'):
            installed = None
        else:
            installed = call(shell, os.environ, 'brl_platform_activate')
            assert installed.returncode == 0, installed.stderr
            for row in manifest['files']:
                path = root / row['path']
                assert hashlib.sha256(path.read_bytes()).hexdigest() == row['newSha256']
                assert path.stat().st_mode & 0o777 == 0o755
            baseline = inventory(root)
            again = call(shell, os.environ, 'brl_platform_activate')
            assert again.returncode == 0 and inventory(root) == baseline, again.stderr
        # Restore even on the success case so the exact old interpreter and
        # fixture finally see r1 external bytes. Full commit is a later gate.
        restored = call(shell, os.environ, 'brl_platform_restore && brl_r1_ram_restore')
        assert restored.returncode == 0, restored.stderr
        for name, content in before.items():
            path = root / name
            assert (path.read_bytes() if path.exists() else None) == content, name
        assert not list((root / 'opt').rglob('*.r0013-installed')), 'installed candidate residue'
        baseline = inventory(root)
        again = call(shell, os.environ, 'brl_platform_restore')
        assert again.returncode == 0 and inventory(root) == baseline, again.stderr
        report = dict(returncode=0, stderr='', phase='restored')
    (root / 'admission-result.json').write_text(json.dumps(report))
    return 1  # Force the real r1 engine's application rollback too.


class PlatformFixture(R1Fixture):
    def update(self, expected=1):
        result = subprocess.run([*self.shell, str(self.engine), *self.update_options], env=self.env,
                                capture_output=True, text=True, timeout=45)
        report = self.root / 'admission-result.json'
        assert result.returncode == expected and report.is_file(), (result.returncode, result.stdout, result.stderr)
        assert hashlib.sha256(self.engine.read_bytes()).hexdigest() == ENGINE_SHA
        return json.loads(report.read_text())

    def __init__(self, shell, mode):
        super().__init__(shell, 'valid')
        helper = self.root / 'opt/libexec/broray-light-updater/runtime-ram.sh'
        helper.unlink()  # This file does not exist in accepted r1.
        for target, source in r0013_platform.TARGETS:
            if source:
                from r0013_inputs import git_bytes
                self.write(self.root / target, git_bytes(source), 0o755)
        command = ' '.join(shlex.quote(x) for x in [sys.executable, '-B', str(Path(__file__).resolve()), '--callback', mode])
        hook = '''#!/bin/sh
if [ "$1" = start ] && [ "$(readlink "$2/current")" = releases/2.0.0-r1 ]; then
    exec CALLBACK
fi
exit 0
'''.replace('CALLBACK', command)
        self.write(self.executable / 'service', hook.encode(), 0o755)

    def make_slot(self, release, installed=True):
        if release != NEW:
            return super().make_slot(release, installed)
        slot = self.root / 'candidate-slot'
        files = r0013_platform.payload()
        files.update({'bin/broray': (b'#!/bin/sh\nexit 0\n', 0o755),
                      'bin/broray-runtime-prepare': (b'#!/bin/sh\nexit 0\n', 0o755),
                      'lib/test.sh': (b'# fixture\n', 0o644),
                      'web-new/home.html': (b'fixture\n', 0o644)})
        base = primitives()
        base.source_app_files = lambda repo, modes: [('app/'+name, data, mode) for name, (data, mode) in sorted(files.items())]
        members, _ = base.slot_payload(self.root, {})
        for name, data, mode in members:
            self.write(slot / name, data, mode)
        return slot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--shell', default='/bin/dash')
    parser.add_argument('--busybox', action='store_true')
    parser.add_argument('--busybox-tools', action='store_true')
    parser.add_argument('--result', type=Path)
    parser.add_argument('--callback')
    args = parser.parse_args()
    if args.callback: raise SystemExit(callback(args.callback))
    assert os.geteuid() == 0, 'Root in disposable Linux CI only'
    shell = [args.shell, 'ash'] if args.busybox else [args.shell]
    if args.busybox_tools:
        import r0013_busybox_fixture
        utility_fixture = r0013_busybox_fixture.enable()
    report = dict(stage='R0013', revision='p30-per-target-platform-stage-journal',
                  scope='REAL_R1_ENGINE_PLATFORM_BYTES_FIXTURE_APP_SERVICE', engineSha256=ENGINE_SHA,
                  sourceSha256=hashlib.sha256(PLATFORM.read_bytes()).hexdigest(), shell=shell,
                  utilities='BusyBox applets' if args.busybox_tools else 'host utilities', tests=[])
    failed = False
    modes = ['activate-restore', 'foreign-target', 'symlink-parent', 'tampered-payload']
    modes += [f'{kind}-{i}-{direction}' for kind in ('partial', 'staged') for i in (4, 5, 6) for direction in ('resume', 'rollback')]
    for mode in modes:
        fixture = PlatformFixture(shell, mode)
        try:
            before = fixture.persistent()
            result = fixture.update(1)
            assert fixture.current() == OLD and fixture.persistent() == before
            report['tests'].append(dict(name=mode, status='PASS', callback=result))
        except Exception as error:
            report['tests'].append(dict(name=mode, status='FAIL', error=str(error)))
            failed = True
            break
        finally:
            fixture.close()
    report['status'] = 'FAIL_FIRST_ERROR' if failed else 'PASS_PLATFORM_ACTIVATION_AND_RESTORE'
    payload = (json.dumps(report, indent=2)+'\n').encode()
    if args.result:
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_bytes(payload)
    print(payload.decode())
    if args.busybox_tools: utility_fixture.cleanup()
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
