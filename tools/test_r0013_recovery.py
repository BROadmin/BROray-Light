#!/usr/bin/env python3
"""Real old-owner death and private-tmpfs loss; never uses a physical router."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import uuid

from test_r0013_live_entry import LiveFixture, ENTRY, C_SOURCE, OLD, NEW, NAMES


def exercise(f, mode):
    journal=f.durable/'legacy-transition.json'
    before=f.persistent()
    service=f.root/'opt/etc/init.d/S24broray-light'
    def recover(expected=0):
        result=subprocess.run([*f.shell,str(service),'recover'],env=f.env,capture_output=True,text=True,timeout=240)
        detail=dict(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,
                    receipt=json.loads(journal.read_bytes()) if journal.exists() else None)
        assert result.returncode==expected,detail
        return detail
    if mode=='finalize':
        f.run_update('update')
        session=(f.app/'run/web-new/sessions'/('a'*48)).read_bytes()
        detail=recover()
        assert detail['receipt']['coordinator']['phase']=='finalized',detail
        assert detail['receipt']['snapshotCleanup']=='complete',detail
        assert not list((f.root/'tmp').glob('broray-light-transition.*'))
        assert (f.app/'run/web-new/sessions'/('a'*48)).read_bytes()==session
        saved=journal.read_bytes()
        recover()
        assert journal.read_bytes()==saved,'Finalized entry rewrote the immutable completion receipt'
        return dict(finalized=True,snapshotsRemoved=True,sessionPreserved=True,idempotent=True)

    hook=f.executable/'service'
    f.write(hook,b'''#!/bin/sh
export BRL_FIXTURE_PIDFILE="$BRORAY_ROOT/run/lighttpd.pid"
/opt/bin/ash "$BRORAY_LIGHT_ROOT_PREFIX/opt/etc/init.d/S24broray-light" "$1" || exit 1
if [ "$1" = start ] && [ "$(readlink "$BRORAY_ROOT/current")" = releases/2.0.0-r1 ]; then
    printf '%s\n' "$$" > "$BRORAY_LIGHT_ROOT_PREFIX/fixture.boundary"
    while [ ! -f "$BRORAY_LIGHT_ROOT_PREFIX/fixture.release" ]; do sleep 0.05; done
fi
''',0o755)
    child=subprocess.Popen([*f.shell,str(f.engine),*f.update_options],env=f.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    f.children.append(child)
    deadline=time.monotonic()+240
    marker=f.root/'fixture.boundary'
    while not marker.exists() and time.monotonic()<deadline:
        if child.poll() is not None:
            out,err=child.communicate();raise AssertionError(dict(returncode=child.returncode,stdout=out,stderr=err))
        time.sleep(.05)
    assert marker.exists(),'Real service hook did not reach activated boundary'
    value=json.loads(journal.read_bytes())
    assert value['legacyPid']==str(child.pid) and value['coordinator']['phase']=='activated',value
    # A non-descendant cannot borrow an exact, still-live old update owner.
    saved=journal.read_bytes()
    recover(1)
    assert journal.read_bytes()==saved,'Busy live-owner check changed the journal'
    os.kill(child.pid,signal.SIGKILL)
    child.wait(timeout=5)
    f.write(f.root/'fixture.release',b'release\n')
    out,err=child.communicate(timeout=5)
    if mode=='foreign-lock':
        lock=f.root/'opt/var/lock/broray-light/global-operation.lock'
        f.write(lock/'foreign',b'never-delete\n')
        recover(1)
        assert (lock/'foreign').read_bytes()==b'never-delete\n'
        assert f.current()==NEW
        return dict(foreignLockRefused=True,foreignObjectPreserved=True)
    if mode=='foreign-slot':
        path=f.app/'releases'/OLD/'app/lib/test.sh'
        f.write(path,b'# unexpected source slot\n',0o644)
        recover(1)
        assert path.read_bytes()==b'# unexpected source slot\n' and f.current()==NEW
        return dict(tamperedSourceRefused=True)
    if mode=='ram-loss':
        f.stop_fixture_processes()
        subprocess.run(['umount',str(f.root/'tmp')],check=True,capture_output=True)
        subprocess.run(['mount','-t','tmpfs','-o','size=64m,mode=1777','tmpfs',str(f.root/'tmp')],check=True,capture_output=True)
        value=json.loads(journal.read_bytes());value['legacyBootId']=str(uuid.uuid4())
        # Fixture-only durable input alteration simulates a different boot.
        # The product always reads /proc/sys/kernel/random/boot_id itself.
        f.write(journal,(json.dumps(value)+'\n').encode())
    detail=recover()
    assert f.current()==OLD and detail['receipt']['coordinator']['phase']=='restored',detail
    assert f.persistent()==before,'Durable user data/config/Xray changed during dead-owner rollback'
    assert not (f.durable/'transaction.json').exists()
    assert not list((f.root/'tmp').glob('broray-light-transition.*'))
    for name in NAMES:assert not (f.app/name).is_symlink(),name
    if mode=='dead-owner':assert (f.app/'run/web-new/sessions'/('a'*48)).read_bytes()==b'preserved-session\n'
    else:assert not (f.app/'run/web-new/sessions'/('a'*48)).exists(),'RAM session unexpectedly survived simulated reboot'
    return dict(rollback=True,sourceRelease=OLD,durablePersistence=True,ramLoss=mode=='ram-loss',snapshotsRemoved=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--shell',default='/bin/dash');p.add_argument('--busybox',action='store_true')
    p.add_argument('--busybox-tools',action='store_true');p.add_argument('--result',type=Path)
    args=p.parse_args();assert os.geteuid()==0
    shell=[args.shell,'ash'] if args.busybox else [args.shell]
    if args.busybox_tools:
        import r0013_busybox_fixture
        utilities=r0013_busybox_fixture.enable()
    ash=Path('/opt/bin/ash');assert not ash.exists() and not ash.is_symlink()
    ash.parent.mkdir(parents=True,exist_ok=True);ash.symlink_to(args.shell)
    records=[];failed=False
    def persist(status):
        report=dict(stage='R0013',revision='p45-dead-owner-and-boot-recovery',status=status,shell=shell,tests=records,
                    entrySha256=hashlib.sha256(ENTRY.read_bytes()).hexdigest(),
                    recoverySha256=hashlib.sha256(ENTRY.with_name('lifecycle-r1-recovery.sh').read_bytes()).hexdigest(),
                    scope='Exact old engine, real S24/entry, actual SIGKILL and private tmpfs remount; fixture app loop/lighttpd/publication OS calls.')
        if args.result:args.result.parent.mkdir(parents=True,exist_ok=True);args.result.write_text(json.dumps(report,indent=2)+'\n')
    persist('IN_PROGRESS')
    try:
        with tempfile.TemporaryDirectory(prefix='r0013-recovery-binary-',dir='/var/tmp') as tmp:
            source=Path(tmp)/'fixture.c';source.write_text(C_SOURCE);binary=Path(tmp)/'fixture'
            subprocess.run(['gcc','-O2','-o',str(binary),str(source)],check=True,capture_output=True)
            for mode in ('finalize','dead-owner','ram-loss','foreign-lock','foreign-slot'):
                fixture=None
                try:
                    fixture=LiveFixture(shell,binary.read_bytes(),'update')
                    records.append(dict(name=mode,status='PASS',detail=exercise(fixture,mode)))
                except Exception as error:records.append(dict(name=mode,status='FAIL',error=str(error)));failed=True
                print(json.dumps(records[-1]),flush=True);persist('FAIL_FIRST_ERROR' if failed else 'IN_PROGRESS')
                if fixture:
                    try:fixture.close()
                    except Exception as error:
                        failed=True;records.append(dict(name=mode+'-cleanup',status='FAIL',error=str(error)))
                        fixture.temp._finalizer.detach();fixture.exec_temp._finalizer.detach()
                        print(json.dumps(records[-1]),flush=True);persist('FAIL_FIRST_ERROR')
                if failed:break
    finally:
        ash.unlink()
        if args.busybox_tools:utilities.cleanup()
    persist('FAIL_FIRST_ERROR' if failed else 'PASS_BOUNDED_RECOVERY')
    raise SystemExit(1 if failed else 0)

if __name__=='__main__':main()
