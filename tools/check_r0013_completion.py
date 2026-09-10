#!/usr/bin/env python3
"""Early real platform rename/SIGKILL boundary, with no product test hook."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import time
import uuid

from test_r0013_live_entry import LiveFixture, C_SOURCE, ENTRY, OLD, NEW
from test_r0013_r1_admission import ENGINE_SHA


def early_anchor(f, ram_loss, negative=None):
    before = f.persistent()
    journal = f.durable/'legacy-transition.json'
    s24 = f.root/'opt/etc/init.d/S24broray-light'
    s23 = f.root/'opt/etc/init.d/S23broray-light-updater'
    old_service = s24.read_bytes()
    old_updater_service = s23.read_bytes()
    marker = f.root/'fixture.anchor'
    invocation = shlex.quote('/usr/bin/mv')
    if len(f.shell) == 2:
        invocation = shlex.quote(f.shell[0])+' mv'
    # The real mv has already succeeded when the wrapper blocks. No application
    # or lifecycle script bytes/manifest are altered for fault injection.
    wrapper = """#!/bin/sh
REAL_MV "$@" || exit $?
case "$*" in
  *"/.S24broray-light.r0013-installed "*"opt/etc/init.d/S24broray-light")
    if [ ! -e "$BRORAY_LIGHT_ROOT_PREFIX/fixture.anchor" ]; then
      printf '%s\\n' "$$" > "$BRORAY_LIGHT_ROOT_PREFIX/fixture.anchor"
      while :; do sleep 0.05; done
    fi
  ;;
esac
""".replace('REAL_MV', invocation)
    f.write(f.tools/'mv', wrapper.encode(), 0o755)
    child = subprocess.Popen([*f.shell, str(f.engine), *f.update_options], env=f.env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    f.children.append(child)
    deadline = time.monotonic()+120
    while not marker.exists() and time.monotonic()<deadline:
        if child.poll() is not None:
            out, err = child.communicate()
            raise AssertionError(dict(returncode=child.returncode, stdout=out, stderr=err))
        time.sleep(.05)
    assert marker.exists(), 'S24 rename boundary was not reached'
    value = json.loads(journal.read_bytes())
    assert value['legacyPid'] == str(child.pid) and value['coordinator']['phase'] == 'prepared', value
    assert 'runtimeTrees' not in value and 'ramTransition' not in value, value
    assert s24.read_bytes() != old_service and s23.read_bytes() == old_updater_service
    assert hashlib.sha256(f.engine.read_bytes()).hexdigest() == ENGINE_SHA
    # Bound cleanup kills the updater and every fixture-owned descendant by
    # PID/start, not by process-name matching. No process survives the boundary.
    f.stop_fixture_processes()
    child.wait(timeout=5)
    child.communicate(timeout=5)
    if ram_loss:
        subprocess.run(['umount', str(f.root/'tmp')], check=True, capture_output=True)
        subprocess.run(['mount', '-t', 'tmpfs', '-o', 'size=64m,mode=1777',
                        'tmpfs', str(f.root/'tmp')], check=True, capture_output=True)
        value['legacyBootId'] = str(uuid.uuid4())
        f.write(journal, (json.dumps(value)+'\n').encode())
    if negative:
        f.ram.mkdir(mode=0o700)
        if negative == 'foreign-child':
            f.write(f.ram/'foreign', b'never-remove\n')
        original_id = (f.ram.stat().st_dev, f.ram.stat().st_ino, f.ram.stat().st_mode)
        original_files = {p.name:p.read_bytes() for p in f.ram.iterdir()}
    command = [*f.shell, str(s23), 'start'] if ram_loss and negative != 'outsider' else [*f.shell, str(s24), 'recover']
    result = subprocess.run(command, env=f.env, capture_output=True, text=True, timeout=240)
    detail = dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr,
                  receipt=json.loads(journal.read_bytes()), current=f.current(),
                  updaterRam=[p.name for p in f.ram.iterdir()] if f.ram.exists() else None)
    if negative:
        assert result.returncode == 1, detail
        assert (f.ram.stat().st_dev, f.ram.stat().st_ino, f.ram.stat().st_mode) == original_id
        assert {p.name:p.read_bytes() for p in f.ram.iterdir()} == original_files
        assert 'oldWorkSurvivor' not in detail['receipt']['recovery'], detail
        return dict(refused=True, namespaceInodeModeAndChildrenPreserved=True, negative=negative)
    assert result.returncode == 0, detail
    assert f.current() == OLD and f.persistent() == before, detail
    assert s24.read_bytes() == old_service and s23.read_bytes() == old_updater_service
    assert not (f.durable/'transaction.json').exists(), detail
    assert not list((f.root/'tmp').glob('broray-light-transition.*')), detail
    assert (f.app/'run/web-new/sessions'/('a'*48)).read_bytes() == b'preserved-session\n'
    if ram_loss:
        survivor = detail['receipt']['recovery']['oldWorkSurvivor']
        assert survivor['preserved'] and survivor['id'] == str(f.ram.stat().st_dev)+':'+str(f.ram.stat().st_ino)
        assert not list(f.ram.iterdir()), 'Old empty survivor was marked or adopted'
    return dict(earlyAnchorRollback=True, realOldS23=ram_loss,
                durablePersistence=True, originalUnmovedSessionPreserved=True,
                snapshotsRemoved=True, privateTmpfsRemounted=ram_loss)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--shell', default='/bin/dash')
    p.add_argument('--busybox', action='store_true')
    p.add_argument('--busybox-tools', action='store_true')
    p.add_argument('--result', type=Path, required=True)
    args = p.parse_args()
    assert os.geteuid() == 0
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

    def persist(status):
        report = dict(stage='R0013', revision='p52-exact-old-recover-empty-namespace-survivor',
                      status=status, shell=shell, tests=records, candidateReady=False,
                      entrySha256=hashlib.sha256(ENTRY.read_bytes()).hexdigest(),
                      scope='Real legacy updater/S23/S24 and rename, fixture OS publication/workload; actual SIGKILL/private tmpfs remount.')
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(json.dumps(report, indent=2)+'\n')

    persist('IN_PROGRESS')
    try:
        with tempfile.TemporaryDirectory(prefix='r0013-completion-binary-', dir='/var/tmp') as tmp:
            source = Path(tmp)/'fixture.c'
            source.write_text(C_SOURCE)
            binary = Path(tmp)/'fixture'
            subprocess.run(['gcc', '-O2', '-o', str(binary), str(source)], check=True, capture_output=True)
            for mode in ('live-rollback-cleanup', 'early-anchor', 'early-anchor-old-s23-boot',
                         'empty-namespace-outsider', 'old-s23-foreign-child'):
                fixture = None
                try:
                    fixture = LiveFixture(shell, binary.read_bytes(),
                                          'health-rollback' if mode == 'live-rollback-cleanup' else 'update')
                    negative = 'outsider' if mode == 'empty-namespace-outsider' else 'foreign-child' if mode == 'old-s23-foreign-child' else None
                    detail = fixture.run_update('health-rollback') if mode == 'live-rollback-cleanup' else early_anchor(
                        fixture, mode != 'early-anchor', negative)
                    records.append(dict(name=mode, status='PASS', detail=detail))
                except Exception as error:
                    records.append(dict(name=mode, status='FAIL', error=str(error)))
                    failed = True
                print(json.dumps(records[-1]), flush=True)
                persist('FAIL_FIRST_ERROR' if failed else 'IN_PROGRESS')
                if fixture:
                    try:
                        fixture.close()
                    except Exception as error:
                        failed = True
                        records.append(dict(name=mode+'-cleanup', status='FAIL', error=str(error)))
                        fixture.temp._finalizer.detach()
                        fixture.exec_temp._finalizer.detach()
                        persist('FAIL_FIRST_ERROR')
                if failed:
                    break
    finally:
        ash.unlink()
        if args.busybox_tools:
            utilities.cleanup()
    persist('FAIL_FIRST_ERROR' if failed else 'PASS_BOUNDED_COMPLETION')
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
