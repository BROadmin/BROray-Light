#!/usr/bin/env python3
"""Complete accepted/prepared app scripts; OS web/publication/Xray fixtures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from build_r0013_release import prepared_app, primitives
from r0013_inputs import baseline_tree
from test_r0013_live_entry import LiveFixture, C_SOURCE, ENTRY, OLD, NEW


class FullFixture(LiveFixture):
    def make_slot(self, release, installed=True):
        slot = self.app/'releases'/release if installed else self.root/('candidate-'+release)
        if release == OLD:
            files = baseline_tree('src/app')
            for name, (data, mode) in baseline_tree('packaging/app-overlay').items():
                assert name in files, 'Unexpected old overlay target: '+name
                files[name] = (data, files[name][1])
        else:
            files = prepared_app()
        base = primitives()
        base.RELEASE_ID = base.CANDIDATE_ID = release
        base.PACKAGE_VERSION = OLD if release == OLD else '2.0.0'
        base.source_app_files = lambda repo, modes: [
            ('app/'+name, data, mode) for name, (data, mode) in sorted(files.items())]
        members, _ = base.slot_payload(self.root, {})
        for name, data, mode in members:
            self.write(slot/name, data, mode)
        return slot

    def app_call(self, action):
        path = self.app/'bin/broray-runtime-prepare' if action == 'prepare-old' else self.root/'opt/etc/init.d/S24broray-light'
        args = [] if action == 'prepare-old' else [action]
        r = subprocess.run([*self.shell, str(path), *args], env=self.env,
                           capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, dict(action=action, returncode=r.returncode, stdout=r.stdout, stderr=r.stderr)
        return r

    def new_command(self, command, expected=0):
        path = self.root/'opt/libexec/broray-light-updater/broray-light-updater.sh'
        r = subprocess.run([*self.shell, str(path), command], env=self.env,
                           capture_output=True, text=True, timeout=240)
        detail = dict(command=command, returncode=r.returncode, stdout=r.stdout, stderr=r.stderr)
        if r.returncode != expected:
            detail['updaterRamState'] = json.loads((self.ram/'state.json').read_bytes()) if (self.ram/'state.json').exists() else None
            detail['transaction'] = json.loads((self.durable/'transaction.json').read_bytes()) if (self.durable/'transaction.json').exists() else None
            detail['daemonLogTail'] = (self.app/'logs/broray-lightd.log').read_text(errors='replace')[-6000:] if (self.app/'logs/broray-lightd.log').exists() else None
        assert r.returncode == expected, detail
        return json.loads(r.stdout) if r.stdout.strip().startswith('{') else {}

    def next_signed_fixture(self, release):
        # Synthetic comparator/rollback fixture only. Never a release artifact.
        self.slot = self.make_slot(release, installed=False)
        self.archive()
        self.index(release)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--shell', default='/bin/dash')
    p.add_argument('--busybox', action='store_true')
    p.add_argument('--busybox-tools', action='store_true')
    p.add_argument('--result', required=True, type=Path)
    args = p.parse_args()
    assert os.geteuid() == 0
    # Workflow unshare --net is mandatory, so application tasks cannot reach
    # any real subscription, probe endpoint, router or production service.
    assert os.readlink('/proc/self/ns/net') != os.readlink('/proc/1/ns/net'), 'Disposable network namespace required'
    shell = [args.shell, 'ash'] if args.busybox else [args.shell]
    if args.busybox_tools:
        import r0013_busybox_fixture
        utilities = r0013_busybox_fixture.enable()
    ash = Path('/opt/bin/ash')
    assert not ash.exists() and not ash.is_symlink()
    ash.parent.mkdir(parents=True, exist_ok=True)
    ash.symlink_to(args.shell)
    records = []
    failed = False
    fixture = None
    current_gate = 'fixture'
    def persist(status):
        report = dict(stage='R0013', revision='p62-busybox-standalone-idle-identity',
                      status=status, shell=shell, tests=records, candidateReady=False,
                      applicationScripts='Complete accepted r1 and current prepared_app; no daemon/CLI substitutions',
                      mockedBoundaries=['lighttpd workload binary','Keenetic publication OS','Xray executable'],
                      network='Private unshared network namespace; signed file:// fixture inputs only',
                      entrySha256=hashlib.sha256(ENTRY.read_bytes()).hexdigest())
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(json.dumps(report, indent=2)+'\n')
    def passed(name, detail):
        records.append(dict(name=name, status='PASS', detail=detail))
        print(json.dumps(records[-1]), flush=True)
        persist('IN_PROGRESS')

    persist('IN_PROGRESS')
    try:
        with tempfile.TemporaryDirectory(prefix='r0013-prepared-binary-', dir='/var/tmp') as tmp:
            source = Path(tmp)/'fixture.c'
            source.write_text(C_SOURCE)
            binary = Path(tmp)/'fixture'
            subprocess.run(['gcc','-O2','-o',str(binary),str(source)], check=True, capture_output=True)
            fixture = FullFixture(shell, binary.read_bytes(), 'update')
            current_gate = 'accepted-r1-runtime-prepare'
            fixture.app_call('prepare-old')
            passed(current_gate, dict(completeAcceptedScripts=True))

            current_gate = 'r1-to-full-prepared-app'
            detail = fixture.run_update('update')
            fixture.app_call('recover')
            receipt = json.loads((fixture.durable/'legacy-transition.json').read_bytes())
            assert receipt['coordinator']['phase'] == 'finalized', receipt
            assert not (fixture.durable/'state.json').exists(), 'Old operational state not retired'
            detail['targetSlotManifestSha256'] = hashlib.sha256((fixture.app/'current/APP-SHA256SUMS').read_bytes()).hexdigest()
            detail['completeAppFileCount'] = len(prepared_app())
            passed(current_gate, detail)

            current_gate = 'equal-version-no-op'
            before = fixture.persistent()
            pid = (fixture.app/'run/broray-lightd.pid').read_bytes()
            result = fixture.new_command('update')
            assert result['relation'] == 'equal', result
            assert (fixture.app/'run/broray-lightd.pid').read_bytes() == pid, 'Equal update restarted daemon'
            assert fixture.persistent() == before
            passed(current_gate, dict(daemonNotRestarted=True, persistentDataIdentical=True))

            current_gate = 'signed-downgrade-refused'
            fixture.index(OLD)
            fixture.new_command('update', 20)
            assert fixture.current() == NEW and fixture.persistent() == before
            passed(current_gate, dict(refusedBeforeSwitch=True))

            current_gate = 'new-updater-full-s24-transition'
            future = '2.0.1-r1'
            fixture.next_signed_fixture(future)
            result = fixture.new_command('update')
            assert fixture.current() == future and fixture.persistent() == before, result
            assert (fixture.app/'releases'/NEW).is_dir()
            passed(current_gate, dict(syntheticTarget=future, completePreparedScripts=True, persistentDataIdentical=True))

            current_gate = 'new-updater-health-rollback'
            rejected = '2.0.2-r1'
            fixture.next_signed_fixture(rejected)
            fixture.env['FIXTURE_HEALTH_FAIL'] = rejected
            fixture.new_command('update', 1)
            assert fixture.current() == future and fixture.persistent() == before
            fixture.new_command('recover')
            assert not (fixture.durable/'transaction.json').exists()
            assert not (fixture.ram/'request.lock').exists()
            assert not list((fixture.root/'tmp/broray-light/run/locks').iterdir())
            assert not list((fixture.ram/'work').iterdir())
            passed(current_gate, dict(sourceRestored=True, persistentDataIdentical=True, updaterScratchClean=True))
    except Exception as error:
        failed = True
        records.append(dict(name=current_gate, status='FAIL', error=str(error)))
        print(json.dumps(records[-1]), flush=True)
        persist('FAIL_FIRST_ERROR')
    finally:
        if fixture:
            try:
                fixture.close()
            except Exception as error:
                failed = True
                records.append(dict(name='fixture-cleanup', status='FAIL', error=str(error)))
                fixture.temp._finalizer.detach()
                fixture.exec_temp._finalizer.detach()
                persist('FAIL_FIRST_ERROR')
        ash.unlink()
        if args.busybox_tools:
            utilities.cleanup()
    persist('FAIL_FIRST_ERROR' if failed else 'PASS_FULL_PREPARED_APP_LIFECYCLE_OS_BOUNDARIES_MOCKED')
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
