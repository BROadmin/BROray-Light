#!/usr/bin/env python3
"""Real prepared daemon idle wait and S24 identity; no application/network work."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

from build_r0013_release import prepared_app
from test_r0013_service import Fixture, C_SOURCE


def process_identity(pid):
    try:
        fields = Path('/proc', str(pid), 'stat').read_text().rsplit(') ', 1)[1].split()
        return None if fields[0] == 'Z' else (fields[1], fields[19])
    except (OSError, IndexError):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--shell', default='/bin/dash')
    parser.add_argument('--busybox', action='store_true')
    parser.add_argument('--busybox-tools', action='store_true')
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    shell = [args.shell, 'ash'] if args.busybox else [args.shell]
    utilities = None
    if args.busybox_tools:
        import r0013_busybox_fixture
        utilities = r0013_busybox_fixture.enable()
    app = prepared_app()
    records = []
    failed = False
    def persist():
        report = dict(stage='R0013', revision='p64-explicit-external-idle-child',
                      status='FAIL_FIRST_ERROR' if failed else 'IN_PROGRESS', tests=records,
                      shell=shell, daemonSha256=hashlib.sha256(app['bin/broray-lightd'][0]).hexdigest(),
                      mockedBoundaries=['Application CLI workload','Xray executable','Keenetic publication'],
                      candidateReady=False)
        if len(records) == 4 and not failed:
            report['status'] = 'PASS_REAL_PREPARED_DAEMON_IDLE_STOP'
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_bytes((json.dumps(report, indent=2)+'\n').encode())
    persist()
    with tempfile.TemporaryDirectory(prefix='r0013-idle-compiler-', dir='/var/tmp') as tmp:
        source = Path(tmp)/'fixture.c'
        source.write_text(C_SOURCE)
        binary = Path(tmp)/'fixture'
        subprocess.run(['gcc','-O2','-o',str(binary),str(source)], check=True, capture_output=True)
        for action in ('TERM','HUP','INT','S24-stop-role'):
            fixture = None
            idle_pid = idle_identity = None
            try:
                fixture = Fixture(shell, binary.read_bytes(), app)
                path = fixture.app/'bin/broray-lightd'
                fixture.write(path, app['bin/broray-lightd'][0], 0o755)
                for name in ('broray-connection-monitor','broray-server-auto-switch','broray-subscriptions','broray-home-snapshot'):
                    fixture.write(fixture.app/'bin'/name, b'#!/bin/sh\nexit 0\n', 0o755)
                with (fixture.ram/'logs/idle-test.log').open('wb') as output:
                    daemon = subprocess.Popen([fixture.interpreter, str(path)], env=fixture.env,
                                              stdout=output, stderr=output, start_new_session=True)
                fixture.children.append(daemon)
                foreign = subprocess.Popen(['sleep','123'], env=fixture.env,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                           start_new_session=True)
                fixture.children.append(foreign)
                deadline = time.monotonic()+5
                observed = []
                while time.monotonic() < deadline:
                    assert daemon.poll() is None, dict(error='Daemon exited before idle',
                        returncode=daemon.returncode,log=(fixture.ram/'logs/idle-test.log').read_text(errors='replace'))
                    for candidate in Path('/proc').glob('[0-9]*/cmdline'):
                        try:
                            argv = candidate.read_bytes().split(b'\0')
                            pid = int(candidate.parent.name)
                            identity = process_identity(pid)
                            if identity and identity[0] == str(daemon.pid):
                                observed.append(dict(pid=pid,argv=[a.decode(errors='replace') for a in argv],identity=identity))
                            if identity and identity[0] == str(daemon.pid) and len(argv) == 3 and argv[1] == b'30':
                                idle_pid, idle_identity = pid, identity
                                break
                        except OSError:
                            pass
                    if idle_pid:
                        break
                    time.sleep(.02)
                assert idle_pid, dict(error='No actual 30-second idle child observed',children=observed[-10:],
                    log=(fixture.ram/'logs/idle-test.log').read_text(errors='replace'))
                # Let the daemon finish capturing the child identity, then
                # interrupt its real builtin wait (not a fake short sleeper).
                time.sleep(.1)
                started = time.monotonic()
                if action == 'S24-stop-role':
                    fixture.call('brl_service_stop_role daemon')
                else:
                    daemon.send_signal(getattr(signal, 'SIG'+action))
                assert daemon.wait(timeout=3) == 0
                elapsed = time.monotonic()-started
                assert elapsed < 3, elapsed
                assert process_identity(idle_pid) != idle_identity, 'Owned sleep survived shutdown'
                assert foreign.poll() is None, 'Unrelated sleep was signalled'
                assert not (fixture.ram/'run/broray-lightd.pid').exists()
                fixture.clean_scratch()
                records.append(dict(name=action,status='PASS',stopSeconds=round(elapsed,3),
                                    ownedSleepReaped=True,foreignSleepUntouched=True))
            except Exception as error:
                failed = True
                records.append(dict(name=action,status='FAIL',error=str(error)))
            finally:
                persist()
                if idle_pid and process_identity(idle_pid) == idle_identity:
                    os.kill(idle_pid, signal.SIGKILL)
                if fixture:
                    fixture.close()
            print(json.dumps(records[-1]), flush=True)
            if failed:
                break
    if utilities:
        utilities.cleanup()
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
