#!/usr/bin/env python3
"""Exact built installer/package and live services in private canonical mounts.

opkg extraction/order, NDMC and native Keenetic HTTP are explicit OS fixtures.
Application, updater, service and web server scripts are not replaced. The exact
installed ARM64 Xray is executed through QEMU, never on a physical router.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

from build_r0013_release import PUBLIC_VERSION, RELEASE_ID, XRAY
from check_r0013_native_auth import NativeServer, NativeHandler, USER, PASSWORD
from test_r0013_build import files
from test_r0013_service import NDMC

APP = Path('/opt/broray-light')
RAM = Path('/tmp/broray-light')
REVISION = 'p63-independent-engineering-build-and-full-clean-package'


def private_namespaces():
    assert os.geteuid() == 0
    for ns in ('mnt', 'net'):
        assert os.readlink('/proc/self/ns/'+ns) != os.readlink('/proc/1/ns/'+ns), ns


def write(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    assert not path.is_symlink()
    path.write_bytes(data)
    path.chmod(mode)


def opkg_adapter(argv):
    private_namespaces()
    assert len(argv) == 4 and argv[0] == '--tmp-dir' and argv[2] == 'install'
    work, package = Path(argv[1]), Path(argv[3])
    assert work == package.parent/'opkg' and work == Path(os.environ['TMPDIR'])
    assert str(package.parent).startswith('/tmp/broray-light-install.')
    assert work.is_dir() and not work.is_symlink() and work.stat().st_mode & 0o777 == 0o700
    carrier = files(package.read_bytes())
    assert set(carrier) == {'debian-binary', 'control.tar.gz', 'data.tar.gz'}
    assert carrier['debian-binary'][0] == b'2.0\n'
    control = files(carrier['control.tar.gz'][0])
    data = files(carrier['data.tar.gz'][0])
    assert ('Version: '+PUBLIC_VERSION+'\n').encode() in control['control'][0]
    for name, (payload, mode) in control.items():
        assert '/' not in name
        write(work/'control'/name, payload, mode)
    subprocess.run(['/opt/bin/ash',str(work/'control/preinst')], check=True)
    for name, (payload, mode) in data.items():
        assert name.startswith('opt/') or name == 'tmp/broray-light-bootstrap/xray-'+XRAY['version'], name
        path = Path('/')/name
        for parent in path.parents:
            assert not parent.is_symlink(), str(parent)
        assert not path.exists() and not path.is_symlink(), 'Adapter refuses overwrite: '+name
        write(path,payload,mode)
    subprocess.run(['/opt/bin/ash',str(work/'control/postinst')], check=True)


class CleanFixture:
    def __init__(self, shell, package):
        private_namespaces()
        self.mounts = []
        self.server = None
        self.shell = shell
        self.env = dict(PATH='/opt/bin:/usr/sbin:/usr/bin:/sbin:/bin', LC_ALL='C.UTF-8',
                        BRORAY_LIGHT_PACKAGE_FILE=str(package), BRL_FIXTURE_NDMC_STATE='/tmp/r0013-os/ndmc.json')
        subprocess.run(['mount','--make-rprivate','/'],check=True,capture_output=True)
        for path in ('/opt','/tmp'):
            subprocess.run(['mount','-t','tmpfs','-o','size=128m,mode='+('1777' if path == '/tmp' else '755'),
                            'r0013-clean-fixture',path],check=True,capture_output=True)
            self.mounts.append((path,os.stat(path).st_dev))
        Path('/opt/bin').mkdir()
        Path('/opt/bin/ash').symlink_to(shell[0])
        from r0013_busybox_fixture import APPLETS
        names = ['hexdump'] if len(shell) == 1 else list(APPLETS)+['hexdump','dd','md5sum']
        for name in names:
            Path('/opt/bin',name).symlink_to('/usr/bin/busybox')
        write(Path('/tmp/r0013-os/ndmc.py'),NDMC.encode())
        write(Path('/opt/bin/ndmc'),b'#!/bin/sh\nexec /usr/bin/python3 /tmp/r0013-os/ndmc.py "$@"\n',0o755)
        adapter = '#!/bin/sh\nexec /usr/bin/python3 '+str(Path(__file__).resolve())+' --opkg-adapter "$@"\n'
        write(Path('/opt/bin/opkg'),adapter.encode(),0o755)
        subprocess.run(['ip','link','set','lo','up'],check=True,capture_output=True)
        subprocess.run(['ip','link','add','Bridge0','type','dummy'],check=True,capture_output=True)
        subprocess.run(['ip','addr','add','192.168.77.1/24','dev','Bridge0'],check=True,capture_output=True)
        subprocess.run(['ip','link','set','Bridge0','up'],check=True,capture_output=True)
        self.server = NativeServer(('127.0.0.1',79),NativeHandler)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.http = build_opener(ProxyHandler({}))

    def command(self, command, expected=0):
        r = subprocess.run(command,env=self.env,capture_output=True,text=True,timeout=120)
        assert r.returncode == expected, dict(command=command,rc=r.returncode,stdout=r.stdout[-6000:],stderr=r.stderr[-6000:])
        return r

    def request(self, endpoint, body=None, cookie=''):
        headers = {'Content-Type':'application/json', 'Cookie':cookie}
        data = None if body is None else json.dumps(body).encode()
        request = Request('http://192.168.77.1:8080/'+endpoint,data=data,headers=headers)
        try:
            response = self.http.open(request, timeout=40)
        except HTTPError as error:
            response = error
        with response:
            payload=response.read()
            return response.status,dict(response.headers),payload

    def close(self):
        if self.server:
            self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)
        # Cleanup is not a passing service assertion. Only exact private app
        # commands/executables are eligible; no host web processes are touched.
        for directory in Path('/proc').glob('[0-9]*'):
            try:
                argv=(directory/'cmdline').read_bytes().split(b'\0')
                exe=os.readlink(directory/'exe')
                if any(a.startswith(b'/opt/broray-light/') for a in argv) or exe.startswith('/opt/broray-light/'):
                    os.kill(int(directory.name),signal.SIGKILL)
            except (OSError,ProcessLookupError):
                pass
        for path,device in reversed(self.mounts):
            assert os.stat(path).st_dev == device
            subprocess.run(['umount',path],check=True,capture_output=True)


def main():
    if len(sys.argv)>1 and sys.argv[1] == '--opkg-adapter':
        opkg_adapter(sys.argv[2:]);return
    p=argparse.ArgumentParser()
    p.add_argument('--build',type=Path,required=True)
    p.add_argument('--shell',default='/bin/dash')
    p.add_argument('--busybox',action='store_true')
    p.add_argument('--result',type=Path,required=True)
    args=p.parse_args()
    root=args.build.resolve();result=args.result.resolve()
    assert not str(root).startswith(('/opt/','/tmp/')) and not str(result).startswith(('/opt/','/tmp/'))
    package=root/('broray-light_'+PUBLIC_VERSION+'_aarch64-3.10.ipk')
    installer=root/('broray-light-install-'+PUBLIC_VERSION+'.sh')
    shell=[args.shell,'ash'] if args.busybox else [args.shell]
    records=[];failed=False;fixture=None;gate='fixture'
    def persist():
        report=dict(stage='R0013',revision=REVISION,status='FAIL_FIRST_ERROR' if failed else 'IN_PROGRESS',
                    shell=shell,tests=records,candidateReady=False,
                    boundary='opkg extraction/order adapter; NDMC and native HTTP fixtures; real app/S23/S24/lighttpd and QEMU ARM64 Xray',
                    artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (package,installer)})
        result.parent.mkdir(parents=True,exist_ok=True)
        result.write_bytes((json.dumps(report,indent=2)+'\n').encode())
    def passed(detail=None):
        records.append(dict(name=gate,status='PASS',detail=detail));persist();print(json.dumps(records[-1]),flush=True)
    persist()
    try:
        fixture=CleanFixture(shell,package)
        gate='exact-installer-preinst-data-postinst-and-live-services'
        fixture.command([*shell,str(installer)])
        for service in ('S23broray-light-updater','S24broray-light'):
            fixture.command([*shell,'/opt/etc/init.d/'+service,'status'])
        assert os.readlink(APP/'current') == 'releases/'+RELEASE_ID
        assert (APP/'config/version').read_text().strip() == RELEASE_ID
        assert not list(Path('/tmp').glob('broray-light-install.*'))
        assert not Path('/tmp/broray-light-bootstrap').exists()
        assert not Path('/opt/var/lock').exists()
        passed(dict(skipServiceStart=False,realLighttpd=True,installerBootstrapScratchClean=True))

        gate='exact-installed-slot-and-arm64-xray'
        fixture.command([*shell,'-c','cd /opt/broray-light/current && sha256sum -c APP-SHA256SUMS'])
        runtime=APP/'runtime/xray'
        assert hashlib.sha256(runtime.read_bytes()).hexdigest() == XRAY['binarySha256']
        assert runtime.stat().st_mode & 0o777 == 0o755
        version=fixture.command(['/usr/bin/qemu-aarch64-static',str(runtime),'version']).stdout.splitlines()[0]
        assert version.startswith('Xray '+XRAY['version']+' '),version
        passed(dict(binarySha256=XRAY['binarySha256'],emulatedVersion=version))

        gate='real-http-native-login-session-home-and-logout'
        status,headers,payload=fixture.request('api/session.cgi')
        assert status==401,(status,payload)
        status,headers,payload=fixture.request('api/login.cgi',{'login':USER,'password':PASSWORD})
        assert status==200 and json.loads(payload)['ok'],(status,payload)
        cookie=headers['Set-Cookie'].split(';')[0]
        for endpoint in ('api/session.cgi','api/home/summary.cgi','api/servers/summary.cgi','api/subscriptions/list.cgi'):
            status,headers,payload=fixture.request(endpoint,cookie=cookie)
            assert status==200,(endpoint,status,payload)
            assert 'no-store' in headers.get('Cache-Control','')
            json.loads(payload)
        assert fixture.request('api/logout.cgi',{},cookie)[0]==200
        assert fixture.request('api/session.cgi',cookie=cookie)[0]==401
        passed(dict(nativeChallengeVerified=fixture.server.accepted==1,transport='actual lighttpd HTTP CGI'))

        gate='service-restart-and-durable-state-persistence'
        durable={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for sub in ('servers','subscriptions','config','runtime')
                 for p in (APP/sub).rglob('*') if p.is_file() and not p.is_symlink()}
        fixture.command([*shell,'/opt/etc/init.d/S24broray-light','restart'])
        fixture.command([*shell,'/opt/etc/init.d/S24broray-light','status'])
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha for p,sha in durable.items())
        fixture.command([*shell,'/opt/etc/init.d/S24broray-light','stop'])
        fixture.command([*shell,'/opt/etc/init.d/S24broray-light','status'],1)
        assert not list((RAM/'tmp').iterdir())
        assert not list((RAM/'run/locks').iterdir())
        passed(dict(durableFilesUnchanged=len(durable),serviceStopped=True))
    except Exception as error:
        failed=True;records.append(dict(name=gate,status='FAIL',error=str(error)));persist();print(json.dumps(records[-1]),flush=True)
    finally:
        if fixture:
            try:fixture.close()
            except Exception as error:
                failed=True;records.append(dict(name='fixture-cleanup',status='FAIL',error=str(error)))
        persist()
    report=json.loads(result.read_bytes())
    report['status']='FAIL_FIRST_ERROR' if failed else 'PASS_EXACT_CLEAN_PACKAGE_LIVE_SERVICES_AND_HTTP_OS_BOUNDARIES_MOCKED'
    result.write_bytes((json.dumps(report,indent=2)+'\n').encode())
    raise SystemExit(1 if failed else 0)


if __name__=='__main__':
    main()
