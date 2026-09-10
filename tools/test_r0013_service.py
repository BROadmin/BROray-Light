#!/usr/bin/env python3
"""Real S24/processes/publication scripts; daemon work and Keenetic OS mocked."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import socket
import subprocess
import tempfile
import time

from r0013_inputs import REPO, git_bytes, app_inputs
from r0013_runtime_paths import compile_runtime

OVERLAY = REPO / 'packaging/r0013-overlay'
SERVICE = OVERLAY / 'system/packaging/opkg/S24broray-light'
PROCESS = OVERLAY / 'shared/service-process.sh'
C_SOURCE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <unistd.h>
#include <sys/stat.h>
static volatile sig_atomic_t done=0;
static void finish(int s){done=s;}
int main(int argc,char **argv){
 if(getenv("BRL_FIXTURE_DAEMONIZE")){if(fork()>0)return 0;close(0);close(1);close(2);}
 signal(SIGTERM,finish);signal(SIGQUIT,finish);signal(SIGINT,finish);
 const char *p=getenv("BRL_FIXTURE_PIDFILE");
 if(p){umask(077);FILE *f=fopen(p,"w");if(!f)return 3;fprintf(f,"%d\n",getpid());fclose(f);}
 while(!done)pause();
 return 0;
}
'''
NDMC = r'''
import json,os,pathlib,sys
p=pathlib.Path(os.environ['BRL_FIXTURE_NDMC_STATE'])
v=json.loads(p.read_text()) if p.exists() else {}
cmd=sys.argv[2] if len(sys.argv)==3 and sys.argv[1]=='-c' else ''
if cmd=='show ndns':
 print('name: fixture\ndomain: keenetic.link\nupdated: yes\naccess: cloud');sys.exit()
if cmd=='show running-config':
 print('interface Bridge0\n    security-level private\n    ip address 192.168.77.1 255.255.255.0\n!')
 if v:
  print('ip http proxy brolight\n    upstream http '+v.get('host','192.168.77.1')+' 8080')
  for key,line in [('domain','domain ndns'),('ssl','ssl redirect'),('security','security-level public')]:
   if v.get(key):print('    '+line)
  print('!')
 sys.exit()
if cmd=='ip http proxy brolight':v['exists']=True
elif cmd.startswith('ip http proxy brolight upstream http '):v['host']=cmd.split()[6]
elif cmd=='ip http proxy brolight domain ndns':v['domain']=True
elif cmd=='ip http proxy brolight ssl redirect':v['ssl']=True
elif cmd=='ip http proxy brolight security-level public':v['security']=True
elif cmd=='no ip http proxy brolight':v={}
elif cmd=='system configuration save':pass
else:sys.exit(126)
p.write_text(json.dumps(v))
'''


class Fixture:
    def __init__(self, shell, binary, app):
        self.temp = tempfile.TemporaryDirectory(prefix='r0013-service-', dir='/var/tmp')
        self.root = Path(self.temp.name)
        self.shell = shell
        self.children=[]
        self.mounted=False
        self.app=self.root/'opt/broray-light'
        self.ram=self.root/'tmp/broray-light'
        (self.root/'tmp').mkdir()
        result=subprocess.run(['mount','-t','tmpfs','-o','size=32m,mode=1777','tmpfs',str(self.root/'tmp')],capture_output=True,text=True)
        if result.returncode:
            self.temp.cleanup()
            raise AssertionError('Private fixture tmpfs mount failed: '+result.stderr)
        self.mounted=True
        self.tools=self.root/'tools';self.tools.mkdir()
        self.ash=self.tools/'ash';self.ash.symlink_to(shell[0])
        # BusyBox uses the executable basename to select ash (no extra argv).
        interpreter=str(self.ash) if len(shell)>1 else shell[0]
        self.interpreter=interpreter
        for path in ('lib','bin','config/system','servers','subscriptions','runtime','backup'):
            (self.app/path).mkdir(parents=True,exist_ok=True,mode=0o700)
        for name in ('runtime-environment.sh','runtime-ram.sh','service-process.sh','web-publication-environment.sh'):
            self.write(self.app/'lib'/name,(OVERLAY/'shared'/name).read_bytes(),0o755)
        self.write(self.app/'lib/xray-process.sh',app['lib/xray-process.sh'][0],0o755)
        self.write(self.app/'config/lighttpd.conf',app['share/defaults/lighttpd.conf'][0],0o600)
        # S24 is real. Daemon's application loop and Xray runtime are bounded
        # fixtures so this test cannot perform proxy or remote network work.
        daemon='#!'+interpreter+'\numask 077\nprintf "%s\\n" "$$" > "$BRL_RAM/run/broray-lightd.pid"\ntrap \'rm -f "$BRL_RAM/run/broray-lightd.pid";exit 0\' TERM INT\nwhile :;do sleep 0.1;done\n'
        self.write(self.app/'bin/broray-lightd',daemon.encode(),0o755)
        self.write(self.app/'bin/broray-runtime-prepare',b'#!/bin/sh\nexit 0\n',0o755)
        self.write(self.app/'bin/broray-xray-control',b'#!/bin/sh\n[ "${BRL_FIXTURE_XRAY_STOP_FAIL:-0}" != 1 ]\n',0o755)
        self.web=self.tools/'lighttpd';self.write(self.web,binary,0o755)
        self.env=dict(os.environ,BRORAY_LIGHT_ROOT_PREFIX=str(self.root),PATH=str(self.tools)+':'+os.environ['PATH'],
                      BRORAY_LIGHT_WEB_TEST_MODE='1',BRORAY_LIGHT_WEB_LAN_IP_OVERRIDE='192.168.77.1',
                      BRORAY_LIGHT_WEB_CONFIG_TEST_COMMAND='/bin/true',BRORAY_LIGHT_WEB_VERIFY_DELAY_SECONDS='0',
                      BRL_FIXTURE_PIDFILE=str(self.ram/'run/lighttpd.pid'),BRL_FIXTURE_DAEMONIZE='1',
                      BRL_FIXTURE_NDMC_STATE=str(self.root/'tmp/ndmc.json'))
        network=self.root/'opt/libexec/broray-light-web-publish'
        for leaf,source in [('start-gate.sh','broray-light-web-start-gate.sh'),('network.sh','broray-light-web-network.sh'),('broray-light-web-publish.sh','broray-light-web-publish.sh')]:
            self.write(network/leaf,(OVERLAY/'system/packaging/opkg'/source).read_bytes(),0o755)
        self.write(network/'policy.sh',git_bytes('packaging/opkg/broray-light-web-publish-policy.sh'),0o755)
        command=' '.join(shlex.quote(x) for x in [*shell,str(network/'broray-light-web-publish.sh')])
        self.ctl=self.root/'opt/bin/broray-light-web-publishctl'
        self.write(self.ctl,('#!/bin/sh\nexec '+command+' "$@"\n').encode(),0o755)
        self.write(self.tools/'ndmc.py',NDMC.encode(),0o644)
        self.write(self.tools/'ndmc',('#!/bin/sh\nexec '+shlex.quote(os.sys.executable)+' '+shlex.quote(str(self.tools/'ndmc.py'))+' "$@"\n').encode(),0o755)
        self.call('. "$ROOT/lib/runtime-environment.sh"',0,guard=False)

    def write(self,path,data,mode=0o600):
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        path.write_bytes(data);path.chmod(mode)

    def call(self,action,expected=0,guard=True):
        code='ROOT="$BRORAY_LIGHT_ROOT_PREFIX/opt/broray-light"; '
        if guard:code+='. "$ROOT/lib/runtime-environment.sh" && . "$ROOT/lib/service-process.sh" && '
        result=subprocess.run([*self.shell,'-c',code+action],env=self.env,capture_output=True,text=True,timeout=30)
        assert result.returncode==expected,(action,result.returncode,result.stdout,result.stderr)
        return result

    def service(self,action,expected=0):
        result=subprocess.run([*self.shell,str(SERVICE),action],env=self.env,capture_output=True,text=True,timeout=40)
        assert result.returncode==expected,(action,result.returncode,result.stdout,result.stderr)
        return result

    def spawn(self,binary,args,role='web',pidfile=True):
        env=self.env.copy();env.pop('BRL_FIXTURE_DAEMONIZE',None)
        target=self.ram/('run/lighttpd.pid' if role=='web' else 'run/web-new/native-auth/nginx.pid')
        target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if pidfile:env['BRL_FIXTURE_PIDFILE']=str(target)
        else:env.pop('BRL_FIXTURE_PIDFILE',None)
        child=subprocess.Popen([str(binary),*map(str,args)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        self.children.append(child)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            if child.poll() is not None:raise AssertionError('Fixture process exited')
            if not pidfile or (target.exists() and target.read_text().strip()==str(child.pid)):break
            time.sleep(.02)
        return child

    def clean_scratch(self):
        assert not list((self.ram/'tmp').iterdir()),'Publication scratch leaked'
        assert not list((self.ram/'run/locks').iterdir()),'Publication locks leaked'
        assert not any((self.app/p).exists() for p in ('run','tmp','logs')),'Persistent runtime directory created'

    def close(self):
        # Kill only fixture-owned processes; failed product stop is NOT replaced
        # by a test PASS. Cleanup never signals outside this fixture root.
        for p in Path('/proc').glob('[0-9]*/cmdline'):
            try:
                args=p.read_bytes().split(b'\0')
                executable=os.readlink(p.parent/'exe') if (p.parent/'exe').exists() else ''
                if any(a.startswith(str(self.root).encode()+b'/') for a in args) or executable.startswith(str(self.root)+'/'):
                    os.kill(int(p.parent.name),signal.SIGKILL)
            except (OSError,ProcessLookupError):pass
        for child in self.children:
            try:child.wait(timeout=3)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        if self.mounted:
            subprocess.run(['umount',str(self.root/'tmp')],check=True,capture_output=True)
        self.temp.cleanup()


def cases():
    for role in ('web','auth'):
        def actual_daemon(f,role=role):
            program=shutil.which('lighttpd' if role=='web' else 'nginx',path=os.environ['PATH'])
            assert program,'Actual daemon dependency unavailable: '+role
            if role=='web':
                binary=f.web;config=f.app/'config/lighttpd.conf';pidfile=f.ram/'run/lighttpd.pid'
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
                text=f'server.document-root = "{f.app}"\nserver.bind = "127.0.0.1"\nserver.port = {port}\nserver.pid-file = "{pidfile}"\nserver.errorlog = "{f.ram}/logs/real-lighttpd.log"\n'
                argv=['-f',str(config)]
            else:
                binary=f.ram/'run/web-new/native-auth/broray-ndm-auth-nginx';config=binary.with_name('nginx.conf');pidfile=binary.with_name('nginx.pid')
                text=f'worker_processes 1;\npid {pidfile};\nerror_log {f.ram}/logs/real-nginx.log notice;\nevents {{ worker_connections 16; }}\n'
                argv=['-p','/','-c',str(config)]
            f.write(binary,Path(program).read_bytes(),0o755);f.write(config,text.encode(),0o600)
            launched=subprocess.run([str(binary),*argv],env=f.env,capture_output=True,text=True,timeout=10)
            assert launched.returncode==0,launched.stderr
            deadline=time.monotonic()+3
            while not pidfile.exists() and time.monotonic()<deadline:time.sleep(.02)
            assert pidfile.is_file(),'Actual daemon did not create PID file'
            pid=pidfile.read_text().strip()
            detail=dict(role=role,pidMode=oct(pidfile.stat().st_mode&0o777),cmdline=Path('/proc',pid,'cmdline').read_bytes().decode('utf-8','backslashreplace'))
            try:
                f.call('brl_service_identity '+role+' '+pid)
                f.call('brl_service_stop_role '+role)
            except AssertionError as error:raise AssertionError(json.dumps(detail)+' '+str(error))
            assert not pidfile.exists(),'PID file was not retired after actual daemon stop'
        yield 'actual-linux-daemon-'+role,actual_daemon
    for mode in ('status-before-publication','invalid-action','ambiguous-lan'):
        def negative(f,mode=mode):
            action='status' if mode=='status-before-publication' else 'invalid' if mode=='invalid-action' else 'ensure'
            if mode=='ambiguous-lan':f.env['BRORAY_LIGHT_WEB_LAN_IP_OVERRIDE']='203.0.113.7'
            result=subprocess.run([str(f.ctl),action],env=f.env,capture_output=True,text=True,timeout=15)
            assert result.returncode!=0,(mode,result.stdout,result.stderr)
            assert not (f.app/'config/web-publish.json').exists()
            f.clean_scratch()
        yield 'publication-negative-'+mode,negative
    def lifecycle(f):
        f.service('start');f.service('status');f.service('start');f.service('restart');f.service('stop');f.service('status',1);f.clean_scratch()
        owner=json.loads((f.app/'config/web-publish.json').read_bytes())
        assert owner['lighttpdConfigSha256']==hashlib.sha256((f.app/'config/lighttpd.conf').read_bytes()).hexdigest()
        result=subprocess.run([str(f.ctl),'delete'],env=f.env,capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
        f.clean_scratch()
    yield 'real-s24-start-status-restart-stop-and-publication',lifecycle
    def exact_web(f):
        c=f.spawn(f.web,['-f',f.app/'config/lighttpd.conf'])
        f.call('brl_service_identity web '+str(c.pid));f.call('brl_service_stop_role web');c.wait(timeout=3)
    yield 'exact-owned-web-stops',exact_web
    for mode in ('writable','symlink','hardlink','public-parent'):
        def unsafe_pid(f,mode=mode):
            c=f.spawn(f.web,['-f',f.app/'config/lighttpd.conf'])
            pid=f.ram/'run/lighttpd.pid'
            if mode=='writable':pid.chmod(0o666)
            elif mode=='symlink':
                saved=pid.with_name('saved.pid');pid.rename(saved);pid.symlink_to(saved)
            elif mode=='hardlink':os.link(pid,pid.with_name('linked.pid'))
            else:pid.parent.chmod(0o755)
            f.call('brl_service_stop_role web',1)
            assert c.poll() is None,'Unsafe PID file was trusted'
        yield 'pid-contract-refuses-'+mode,unsafe_pid
    for mode in ('config-suffix','validator','extra-arg','foreign-exe','unrecorded'):
        def reject(f,mode=mode):
            binary=f.web;args=['-f',str(f.app/'config/lighttpd.conf')]
            if mode=='config-suffix':args[-1]+='.foreign'
            if mode=='validator':args.insert(0,'-tt')
            if mode=='extra-arg':args.append('foreign')
            if mode=='foreign-exe':
                binary=f.tools/'foreign-lighttpd';f.write(binary,f.web.read_bytes(),0o755)
            c=f.spawn(binary,args,pidfile=mode!='unrecorded')
            if mode!='unrecorded':f.call('brl_service_identity web '+str(c.pid),1)
            f.call('brl_service_stop_role web',1)
            assert c.poll() is None,'Foreign process signalled'
        yield 'web-refuses-'+mode,reject
    def duplicate(f):
        a=f.spawn(f.web,['-f',f.app/'config/lighttpd.conf'])
        b=f.spawn(f.web,['-f',f.app/'config/lighttpd.conf'],pidfile=False)
        f.call('brl_service_stop_role web',1)
        assert a.poll() is None and b.poll() is None
    yield 'duplicate-web-fails-closed',duplicate
    for mode in ('exact','config-suffix','foreign-exe'):
        def auth(f,mode=mode):
            binary=f.ram/'run/web-new/native-auth/broray-ndm-auth-nginx';f.write(binary,f.web.read_bytes(),0o700)
            args=['-p','/','-c',str(binary.with_name('nginx.conf'))]
            if mode=='config-suffix':args[-1]+='.foreign'
            if mode=='foreign-exe':
                binary=f.tools/'foreign-nginx';f.write(binary,f.web.read_bytes(),0o755)
            c=f.spawn(binary,args,role='auth')
            f.call('brl_service_stop_role auth',0 if mode=='exact' else 1)
            if mode=='exact':c.wait(timeout=3)
            else:assert c.poll() is None
        yield 'native-auth-'+mode,auth
    def fence(f):
        f.call('brl_lock_acquire request')
        # Dead request owners are reaped by the shared primitive; a live owner
        # fixture demonstrates refusal without issuing any NDMC write.
        ready=f.root/'tmp/fence-ready'
        code='ROOT="$BRORAY_LIGHT_ROOT_PREFIX/opt/broray-light"; . "$ROOT/lib/runtime-environment.sh"; brl_lock_acquire request || exit; touch "'+str(ready)+'"; sleep 15'
        c=subprocess.Popen([*f.shell,'-c',code],env=f.env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True);f.children.append(c)
        deadline=time.monotonic()+3
        while not ready.exists() and time.monotonic()<deadline:time.sleep(.02)
        assert ready.exists()
        r=subprocess.run([str(f.ctl),'ensure'],env=f.env,capture_output=True,text=True,timeout=10)
        assert r.returncode!=0 and not Path(f.env['BRL_FIXTURE_NDMC_STATE']).exists()
    yield 'publication-respects-live-updater-request',fence


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--shell',default='/bin/dash');parser.add_argument('--busybox',action='store_true');parser.add_argument('--busybox-tools',action='store_true');parser.add_argument('--result',type=Path)
    args=parser.parse_args();assert os.geteuid()==0
    shell=[args.shell,'ash'] if args.busybox else [args.shell]
    if args.busybox_tools:
        import r0013_busybox_fixture
        utilities=r0013_busybox_fixture.enable()
    records=[];failed=False
    app=compile_runtime(app_inputs())
    with tempfile.TemporaryDirectory(prefix='r0013-service-compiler-') as temporary:
        code=Path(temporary)/'process.c';code.write_text(C_SOURCE)
        out=Path(temporary)/'process'
        subprocess.run(['gcc','-Wall','-O2',str(code),'-o',str(out)],check=True,capture_output=True)
        binary=out.read_bytes()
        for name,case in cases():
            fixture=None
            try:
                fixture=Fixture(shell,binary,app);case(fixture);records.append(dict(name=name,status='PASS'))
            except Exception as error:
                records.append(dict(name=name,status='FAIL',error=str(error)));failed=True;break
            finally:
                if fixture:fixture.close()
    report=dict(stage='R0013',revision='p39-private-root-owned-daemon-pid-contract',status='FAIL_FIRST_ERROR' if failed else 'PASS_SCOPED_SERVICE_AND_PUBLICATION',shell=shell,tests=records,
                scope='Actual lighttpd/nginx and real S24/publication/private tmpfs; application daemon loop, Xray and Keenetic commands mocked. Not full r1/boot acceptance.',sourceSha256={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (SERVICE,PROCESS)})
    payload=(json.dumps(report,indent=2)+'\n').encode()
    if args.result:args.result.parent.mkdir(parents=True,exist_ok=True);args.result.write_bytes(payload)
    print(payload.decode())
    if args.busybox_tools:utilities.cleanup()
    raise SystemExit(1 if failed else 0)

if __name__=='__main__':main()
