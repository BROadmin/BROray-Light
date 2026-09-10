#!/usr/bin/env python3
"""Exact r1 updater + cross-filesystem runtime snapshots and interruption tests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from test_r0013_web_config import WebFixture
from test_r0013_platform import HELPERS
from r0013_inputs import REPO

TREE=HELPERS[-1].with_name('lifecycle-r1-runtime-trees.sh')
LIBRARIES=[*HELPERS,HELPERS[-1].with_name('service-process.sh'),REPO/'packaging/r0013-overlay/app/lib/xray-process.sh',TREE]
NAMES=('run','logs','tmp','update')


def call(shell,env,action):
    code='; '.join('. "$'+str(i)+'"' for i in range(1,len(LIBRARIES)+1))+'; '+action
    return subprocess.run([*shell,'-c',code,'fixture',*map(str,LIBRARIES)],env=env,capture_output=True,text=True,timeout=60)


def snapshot(app):
    result={}
    for name in NAMES:
        root=app/name
        if not root.exists() and not root.is_symlink():continue
        for p in [root,*sorted(root.rglob('*'))]:
            result[str(p.relative_to(app))]=dict(mode=p.lstat().st_mode,
                value=os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
    return result


def callback(mode):
    root=Path(os.environ['BRORAY_LIGHT_ROOT_PREFIX']);app=root/'opt/broray-light'
    shell=json.loads(os.environ['R0013_FIXTURE_SHELL']);journal=root/'opt/var/lib/broray-light-updater/legacy-transition.json'
    baseline=snapshot(app)
    promoted=call(shell,os.environ,'brl_r1_ram_promote');assert promoted.returncode==0,promoted.stderr
    restore_fault=None
    if mode=='foreign-symlink':
        p=app/'tmp/probe.json';data=p.read_bytes();p.unlink();p.symlink_to('/etc/passwd')
        def restore_fault():p.unlink();p.write_bytes(data);p.chmod(0o600)
    elif mode=='foreign-owner':
        p=app/'logs/service.log';os.chown(p,1000,1000)
        def restore_fault():os.chown(p,0,0)
    elif mode=='foreign-live-pid':
        p=app/'run/lighttpd.pid';p.write_text(str(os.getpid())+'\n');p.chmod(0o644)
        def restore_fault():p.unlink()
    if restore_fault:
        before=snapshot(app)
        result=call(shell,os.environ,'brl_tree_promote')
        assert result.returncode==1 and snapshot(app)==before,(result.returncode,result.stderr)
        restore_fault()
    else:
        result=call(shell,os.environ,'brl_tree_prepare_all');assert result.returncode==0,result.stderr
        planned=json.loads(journal.read_bytes())
        backup=root/'tmp'/planned['ramTransition']['directory']/'runtime-r1'
        if mode=='partial-backup':
            (backup/'tmp/probe.json').write_bytes(b'partial')
        elif mode=='partial-destination':
            p=root/'tmp/broray-light/tmp/probe.json';p.write_bytes(b'partial');p.chmod(0o600)
            planned['runtimeTrees']['tmp']['ramDestinationId']=f'{p.parent.stat().st_dev}:{p.parent.stat().st_ino}'
            journal.write_text(json.dumps(planned))
        elif mode=='partial-original-removal':
            (app/'run/status.json').unlink()
        elif mode=='whole-original-removed':
            (app/'tmp/probe.json').unlink();(app/'tmp').rmdir()
        if mode!='prepared-rollback':
            result=call(shell,os.environ,'brl_tree_promote');assert result.returncode==0,result.stderr
            for name in NAMES:
                assert (app/name).is_symlink() and os.readlink(app/name)==str(root/'tmp/broray-light'/name)
            for relative,entry in baseline.items():
                if entry['value'] is not None:
                    assert hashlib.sha256((app/relative).read_bytes()).hexdigest()==entry['value'],relative
            raw=journal.read_bytes()
            result=call(shell,os.environ,'brl_tree_promote');assert result.returncode==0 and journal.read_bytes()==raw,result.stderr
        if mode=='partial-restore-candidate':
            staged=app/'.run.r0013-restored';staged.mkdir(mode=0o700)
            p=staged/'status.json';p.write_bytes(b'partial');p.chmod(0o600)
            planned=json.loads(journal.read_bytes());st=staged.stat()
            planned['runtimeTrees']['run']['restoreId']=f'{st.st_dev}:{st.st_ino}'
            journal.write_text(json.dumps(planned))
        result=call(shell,os.environ,'brl_tree_restore');assert result.returncode==0,result.stderr
        assert snapshot(app)==baseline,'Old operational content/modes not restored exactly'
        if mode=='restore-rename-before-receipt':
            planned=json.loads(journal.read_bytes());planned['runtimeTrees']['run']['phase']='restoring'
            journal.write_text(json.dumps(planned))
        result=call(shell,os.environ,'brl_tree_restore');assert result.returncode==0,result.stderr
        assert snapshot(app)==baseline
    result=call(shell,os.environ,'brl_r1_ram_restore');assert result.returncode==0,result.stderr
    assert snapshot(app)==baseline
    (root/'admission-result.json').write_text(json.dumps(dict(status='PASS',mode=mode,crossFilesystem=True)))
    return 1 # Exercise actual old updater rollback too; service boundary mocked.


class TreeFixture(WebFixture):
    root_parent='/var/tmp'
    mount_tmpfs=True
    update_timeout=180

    def __init__(self,shell,mode):
        super().__init__(shell,'activate-restore')
        assert self.app.stat().st_dev!=(self.root/'tmp').stat().st_dev,'Fixture is not cross-filesystem'
        for name in NAMES:(self.app/name).mkdir(mode=0o755)
        for name in ('web-new','web-new/sessions'):(self.app/'run'/name).mkdir(mode=0o700)
        for relative,data in [('run/status.json',b'{"healthy":true}\n'),('run/web-new/sessions/'+('a'*48),b'{"fixtureSession":true}\n'),
                              ('logs/service.log',b'old log\n'),('tmp/probe.json',b'{"probe":"old"}\n'),('update/state.json',b'{"oldState":true}\n')]:
            self.write(self.app/relative,data,0o600)
        command=' '.join(shlex.quote(x) for x in [sys.executable,'-B',str(Path(__file__).resolve()),'--callback',mode])
        hook='''#!/bin/sh
if [ "$1" = start ] && [ "$(readlink "$2/current")" = releases/2.0.0-r1 ]; then
 exec CALLBACK
fi
exit 0
'''.replace('CALLBACK',command)
        self.write(self.executable/'service',hook.encode(),0o755)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--shell',default='/bin/dash');parser.add_argument('--busybox',action='store_true');parser.add_argument('--busybox-tools',action='store_true');parser.add_argument('--result',type=Path);parser.add_argument('--callback')
    args=parser.parse_args()
    if args.callback:raise SystemExit(callback(args.callback))
    assert os.geteuid()==0
    shell=[args.shell,'ash'] if args.busybox else [args.shell]
    if args.busybox_tools:
        import r0013_busybox_fixture
        utilities=r0013_busybox_fixture.enable()
    records=[];failed=False
    modes=['promote-restore','foreign-symlink','foreign-owner','foreign-live-pid','prepared-rollback','partial-backup','partial-destination',
           'partial-original-removal','whole-original-removed','partial-restore-candidate','restore-rename-before-receipt']
    for mode in modes:
        fixture=None
        try:
            fixture=TreeFixture(shell,mode);before=fixture.persistent();runtime=snapshot(fixture.app)
            result=fixture.update(1)
            assert fixture.current()=='1.0.0-r1' and fixture.persistent()==before and snapshot(fixture.app)==runtime
            records.append(dict(name=mode,status='PASS',callback=result))
        except Exception as error:records.append(dict(name=mode,status='FAIL',error=str(error)));failed=True;break
        finally:
            if fixture:fixture.close()
    report=dict(stage='R0013',revision='p40-legacy-runtime-tree-quiescence-and-ram-handoff',status='FAIL_FIRST_ERROR' if failed else 'PASS_RUNTIME_TREE_HANDOFF',tests=records,
                sourceSha256=hashlib.sha256(TREE.read_bytes()).hexdigest(),shell=shell,
                scope='Actual r1 updater + real cross-filesystem RAM copy/rollback and foreign PID refusal; application/service boundary mocked. Boot RAM loss not yet integrated.')
    payload=(json.dumps(report,indent=2)+'\n').encode()
    if args.result:args.result.parent.mkdir(parents=True,exist_ok=True);args.result.write_bytes(payload)
    print(payload.decode())
    if args.busybox_tools:utilities.cleanup()
    raise SystemExit(1 if failed else 0)

if __name__=='__main__':main()
