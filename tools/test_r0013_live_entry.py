#!/usr/bin/env python3
"""Actual unchanged r1 updater + both real S24 implementations; OS/app loop fixtures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import tempfile
import time

from build_r0013_release import prepared_app, primitives
from r0013_inputs import REPO, git_bytes
from test_r0013_web_config import WebFixture
from test_r0013_service import C_SOURCE
from test_r0013_runtime_trees import snapshot, NAMES
from test_r0013_updater_ram import OLD, NEW

OVERLAY=REPO/'packaging/r0013-overlay'
ENTRY=OVERLAY/'shared/lifecycle-r1-entry.sh'


class LiveFixture(WebFixture):
    root_parent='/var/tmp'
    mount_tmpfs=True

    def __init__(self,shell,binary,mode):
        self.interpreter='/opt/bin/ash'
        super().__init__(shell,'valid')
        self.tools=self.executable/'tools';self.tools.mkdir()
        self.write(self.tools/'lighttpd',binary,0o755)
        for name in NAMES:(self.app/name).mkdir(mode=0o755)
        for name in ('web-new','web-new/sessions'):(self.app/'run'/name).mkdir(mode=0o700)
        self.write(self.app/'run/web-new/sessions'/('a'*48),b'preserved-session\n')
        self.write(self.app/'logs/old.log',b'old-log\n')
        self.write(self.app/'tmp/probe.json',b'{"old":true}\n')
        self.write(self.app/'update/state.json',b'{"old":true}\n')
        # Accepted r1 runtime-prepare always seeds these before service startup.
        # Model an installed/running r1, not a partial synthetic installation.
        for name in ('settings.json','server-auto-switch.json'):
            self.write(self.app/'config/system'/name,git_bytes('src/app/share/defaults/'+name),0o644)
        for name in ('lib','web-new','share'):
            (self.app/name).symlink_to('current/app/'+name,target_is_directory=True)
        # All lifecycle scripts/legacy engine bytes are unmodified. Only OS
        # publication and service workload dependencies are explicitly mocked.
        self.write(self.root/'opt/bin/broray-light-web-publishctl',b'''#!/bin/sh
printf '%s\\n' "$1" >> "$BRORAY_LIGHT_ROOT_PREFIX/fixture.publication-calls"
case "$1" in status|ensure) exit 0 ;; *) exit 1 ;; esac
''',0o755)
        script='''#!/bin/sh
export BRL_FIXTURE_PIDFILE="$BRORAY_ROOT/run/lighttpd.pid"
exec /opt/bin/ash "$BRORAY_LIGHT_ROOT_PREFIX/opt/etc/init.d/S24broray-light" "$1"
'''
        self.write(self.executable/'service',script.encode(),0o755)
        self.write(self.executable/'health',b'''#!/bin/sh
[ "$1" != "${FIXTURE_HEALTH_FAIL:-none}" ] || exit 1
exec /opt/bin/ash "$BRORAY_LIGHT_ROOT_PREFIX/opt/etc/init.d/S24broray-light" status
''',0o755)
        self.env.update(BRORAY_ROOT=str(self.app),BRORAY_BASE=str(self.app),
                        BRORAY_LIGHT_WEB_PUBLISH_CTL=str(self.root/'opt/bin/broray-light-web-publishctl'),
                        BRORAY_LIGHT_WEB_START_GATE_LIBRARY=str(self.root/'opt/libexec/broray-light-web-publish/start-gate.sh'),
                        BRL_FIXTURE_DAEMONIZE='1',BRL_FIXTURE_PIDFILE=str(self.app/'run/lighttpd.pid'),
                        PATH=str(self.tools)+':'+os.environ['PATH'])
        if mode=='health-rollback':self.env['FIXTURE_HEALTH_FAIL']=NEW

    def make_slot(self,release,installed=True):
        slot=self.app/'releases'/release if installed else self.root/'candidate-slot'
        daemon=b'''#!/opt/bin/ash
umask 077
pidfile="$BRORAY_ROOT/run/broray-lightd.pid"
printf '%s\\n' "$$" > "$pidfile" || exit 1
trap 'rm -f "$pidfile";exit 0' TERM INT
while :;do sleep 0.1;done
'''
        files=prepared_app() if release==NEW else {
            'bin/broray':(b'#!/opt/bin/ash\nexit 0\n',0o755),
            'bin/broray-runtime-prepare':(b'#!/opt/bin/ash\nexit 0\n',0o755),
            'lib/test.sh':(b'# fixture\n',0o644),
            'web-new/home.html':(b'fixture\n',0o644),
            'share/defaults/version':((release+'\n').encode(),0o644)}
        files.update({'bin/broray-lightd':(daemon,0o755),
                      'bin/broray-xray-control':(b'#!/opt/bin/ash\nexit 0\n',0o755),
                      'bin/broray-subscriptions':(b'#!/opt/bin/ash\n[ "$1" = deduplicate ]\n',0o755)})
        base=primitives()
        base.RELEASE_ID=base.CANDIDATE_ID=base.PACKAGE_VERSION=release
        base.source_app_files=lambda repo,modes:[('app/'+name,data,mode) for name,(data,mode) in sorted(files.items())]
        members,_=base.slot_payload(self.root,{})
        for name,data,mode in members:self.write(slot/name,data,mode)
        return slot

    def run_update(self,mode):
        before=self.persistent()
        config=before['config/lighttpd.conf'];owner=json.loads(before['config/web-publish.json'])
        old_session=(self.app/'run/web-new/sessions'/('a'*48)).read_bytes()
        result=subprocess.run([*self.shell,str(self.engine),*self.update_options],env=self.env,
                              capture_output=True,text=True,timeout=240)
        expected=1 if mode=='health-rollback' else 0
        journal=self.durable/'legacy-transition.json'
        detail=dict(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,
                    receipt=json.loads(journal.read_bytes()) if journal.exists() else None)
        assert result.returncode==expected,detail
        assert self.current()==(OLD if mode=='health-rollback' else NEW),detail
        if mode=='health-rollback':
            assert detail['receipt']['coordinator']['phase']=='restored',detail
            after=self.persistent()
            differences=dict(created=sorted(set(after)-set(before)),removed=sorted(set(before)-set(after)),
                             changed=sorted(name for name in before.keys()&after.keys() if before[name]!=after[name]))
            assert after==before,'Durable configuration/data not restored byte-for-byte: '+json.dumps(differences)
            for name in NAMES:assert not (self.app/name).is_symlink(),name
            assert detail['receipt']['snapshotCleanup']=='complete',detail
            assert not list((self.root/'tmp').glob('broray-light-transition.*')),'Live rollback leaked transition snapshots'
        else:
            assert detail['receipt']['coordinator']['phase']=='activated',detail
            expected_config=config.replace(b'"/opt/broray-light/run/lighttpd.pid"',b'"/tmp/broray-light/run/lighttpd.pid"').replace(
                b'"/opt/broray-light/logs/lighttpd-error.log"',b'"/tmp/broray-light/logs/lighttpd-error.log"')
            after=self.persistent()
            assert after.pop('config/lighttpd.conf')==expected_config
            updated_owner=json.loads(after.pop('config/web-publish.json'))
            owner['lighttpdConfigSha256']=hashlib.sha256(expected_config).hexdigest()
            assert updated_owner==owner
            before.pop('config/lighttpd.conf');before.pop('config/web-publish.json')
            # New defaults are expected; pre-existing user data is immutable.
            assert all(after[name]==data for name,data in before.items())
            for name in NAMES:assert (self.app/name).is_symlink(),name
            assert not (self.durable/'transaction.json').exists()
        assert (self.app/'run/web-new/sessions'/('a'*48)).read_bytes()==old_session
        assert not (self.root/'opt/var/lock/broray-light/global-operation.lock').exists()
        assert not (self.root/'opt/var/lock/broray-light-updater/request.lock').exists()
        return dict(returncode=result.returncode,current=self.current(),coordinatorPhase=detail['receipt']['coordinator']['phase'],
                    legacyUpdaterCompleted=True,sessionPreserved=True)

    def stop_fixture_processes(self):
        processes={};owned=set()
        for path in Path('/proc').glob('[0-9]*/cmdline'):
            try:
                stat=(path.parent/'stat').read_text().rsplit(') ',1)[1].split()
                pid=int(path.parent.name);processes[pid]=(int(stat[1]),stat[19])
                args=path.read_bytes().split(b'\0')
                exe=os.readlink(path.parent/'exe') if (path.parent/'exe').exists() else ''
                if any(a.startswith(str(self.root).encode()+b'/') or a.startswith(str(self.executable).encode()+b'/') for a in args) or exe.startswith(str(self.executable)+'/'):
                    owned.add(pid)
            except OSError:pass
        # Descendants may inherit a RAM log descriptor without a product path
        # in argv (e.g. the daemon fixture's sleep). Bind their PID/start first.
        while True:
            expanded=owned|{pid for pid,(parent,start) in processes.items() if parent in owned}
            if expanded==owned:break
            owned=expanded
        def live(pid):
            try:
                row=Path('/proc',str(pid),'stat').read_text().rsplit(') ',1)[1].split()
                return row[0]!='Z' and row[19]==processes[pid][1]
            except OSError:return False
        assert os.getpid() not in owned,'Fixture cleanup included its own runner'
        for pid in owned:
            if live(pid):
                try:os.kill(pid,signal.SIGKILL)
                except ProcessLookupError:pass
        deadline=time.monotonic()+3
        while any(live(pid) for pid in owned) and time.monotonic()<deadline:time.sleep(.02)
        assert not any(live(pid) for pid in owned),'Fixture-owned process did not exit'
        def ram_references():
            refs=[]
            prefix=str(self.root/'tmp')
            for proc in Path('/proc').glob('[0-9]*'):
                try:
                    links=[proc/'cwd',proc/'root',proc/'exe',*list((proc/'fd').iterdir())]
                except OSError:continue
                for link in links:
                    try:value=os.readlink(link)
                    except OSError:continue
                    if value==prefix or value.startswith(prefix+'/'):
                        refs.append(dict(pid=int(proc.name),object=str(link.relative_to(proc)),target=value))
            return refs
        deadline=time.monotonic()+3
        refs=ram_references()
        while refs and time.monotonic()<deadline:
            time.sleep(.05);refs=ram_references()
        assert not refs,'Private tmpfs holders did not drain: '+json.dumps(refs)

    def close(self):
        self.stop_fixture_processes()
        super().close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--shell',default='/bin/dash')
    parser.add_argument('--busybox',action='store_true');parser.add_argument('--busybox-tools',action='store_true');parser.add_argument('--result',type=Path)
    args=parser.parse_args();assert os.geteuid()==0
    shell=[args.shell,'ash'] if args.busybox else [args.shell]
    if args.busybox_tools:
        import r0013_busybox_fixture
        utilities=r0013_busybox_fixture.enable()
    ash=Path('/opt/bin/ash');assert not ash.exists() and not ash.is_symlink(),'Fixture interpreter path is occupied'
    ash.parent.mkdir(parents=True,exist_ok=True);ash.symlink_to(args.shell)
    records=[];failed=False
    def persist():
        report=dict(stage='R0013',revision='p44-accepted-r1-config-fixture-and-real-health-status',
                    status='FAIL_FIRST_ERROR' if failed else 'IN_PROGRESS',shell=shell,tests=records,
                    sourceSha256=hashlib.sha256(ENTRY.read_bytes()).hexdigest(),
                    scope='Real r1/new S24 and entry; daemon workload/lighttpd/publication OS calls mocked. Boot/finalization not integrated.')
        if args.result:
            args.result.parent.mkdir(parents=True,exist_ok=True)
            args.result.write_text(json.dumps(report,indent=2)+'\n')
    persist()
    try:
        with tempfile.TemporaryDirectory(prefix='r0013-live-binary-',dir='/var/tmp') as tmp:
            source=Path(tmp)/'fixture.c';source.write_text(C_SOURCE)
            binary=Path(tmp)/'fixture'
            subprocess.run(['gcc','-O2','-o',str(binary),str(source)],check=True,capture_output=True)
            for mode in ('update','health-rollback'):
                fixture=None
                try:
                    fixture=LiveFixture(shell,binary.read_bytes(),mode)
                    detail=fixture.run_update(mode)
                    records.append(dict(name=mode,status='PASS',detail=detail))
                except Exception as error:records.append(dict(name=mode,status='FAIL',error=str(error)));failed=True
                print(json.dumps(records[-1]),flush=True)
                persist() # Primary evidence must survive a cleanup exception.
                if fixture:
                    try:fixture.close()
                    except Exception as error:
                        failed=True;records.append(dict(name=mode+'-cleanup',status='FAIL',error=str(error)))
                        # Do not recursively walk a still-mounted fixture during
                        # Python's implicit finalizer. CI retains it for logs.
                        fixture.temp._finalizer.detach()
                        fixture.exec_temp._finalizer.detach()
                        persist();print(json.dumps(records[-1]),flush=True)
                if failed:break
    finally:
        ash.unlink()
        if args.busybox_tools:utilities.cleanup()
    report=dict(stage='R0013',revision='p44-accepted-r1-config-fixture-and-real-health-status',
                status='FAIL_FIRST_ERROR' if failed else 'PASS_LIVE_R1_SERVICE_TRANSITION',
                shell=shell,tests=records,sourceSha256=hashlib.sha256(ENTRY.read_bytes()).hexdigest(),
                scope='Real signed fixture r1 update engine, cached r1 S24, new runtime-prepare and new S24, cross-filesystem RAM handoff. Daemon workload, lighttpd and publication OS calls mocked. Boot/finalization not yet integrated.')
    payload=(json.dumps(report,indent=2)+'\n').encode()
    if args.result:args.result.parent.mkdir(parents=True,exist_ok=True);args.result.write_bytes(payload)
    print(payload.decode());raise SystemExit(1 if failed else 0)

if __name__=='__main__':main()
