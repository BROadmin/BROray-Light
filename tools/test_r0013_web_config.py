#!/usr/bin/env python3
"""Real r1 updater, Light config/receipt migration and exact rollback bytes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from r0013_inputs import git_bytes
from test_r0013_platform import PlatformFixture, HELPERS
from test_r0013_r1_admission import inventory

WEB = HELPERS[-1].with_name('lifecycle-r1-web-config.sh')
POLICY_SHA = 'e3e0e68b10ef69fce1c504f2689d1ecbd3f8b6b78ee6e7ab03d8ea73d63607dc'


def call(shell, env, action):
    code = '; '.join('. "$'+str(i)+'"' for i in range(1,7))+'; '+action
    return subprocess.run([*shell,'-c',code,'fixture',*map(str,[*HELPERS,WEB])],env=env,
                          capture_output=True,text=True,timeout=45)


def callback(mode):
    root = Path(os.environ['BRORAY_LIGHT_ROOT_PREFIX'])
    shell = json.loads(os.environ['R0013_FIXTURE_SHELL'])
    config = root / 'opt/broray-light/config/lighttpd.conf'
    owner = config.with_name('web-publish.json')
    journal = root / 'opt/var/lib/broray-light-updater/legacy-transition.json'
    config_bytes, owner_bytes = config.read_bytes(), owner.read_bytes()
    config_mode = config.stat().st_mode & 0o777
    promoted = call(shell,os.environ,'brl_r1_ram_promote')
    assert promoted.returncode == 0, promoted.stderr
    fault_restore = None
    if mode == 'missing-owner':
        owner.unlink()
        def fault_restore():
            owner.write_bytes(owner_bytes)
            owner.chmod(0o600)
    elif mode == 'owner-sha-mismatch':
        value=json.loads(owner_bytes); value['lighttpdConfigSha256']='0'*64
        owner.write_text(json.dumps(value))
        fault_restore=lambda:owner.write_bytes(owner_bytes)
    elif mode == 'duplicate-pid-directive':
        config.write_bytes(config_bytes+b'  server.pid-file = "/opt/foreign.pid"\n')
        value=json.loads(owner_bytes); value['lighttpdConfigSha256']=hashlib.sha256(config.read_bytes()).hexdigest()
        owner.write_text(json.dumps(value))
        def fault_restore():
            config.write_bytes(config_bytes); owner.write_bytes(owner_bytes)
    elif mode == 'config-symlink':
        saved=config.with_name('fixture-saved-config');config.rename(saved);config.symlink_to(saved)
        def fault_restore():
            config.unlink();saved.rename(config)
    baseline=inventory(root)
    if fault_restore:
        result=call(shell,os.environ,'brl_web_config_activate')
        assert result.returncode == 1 and inventory(root)==baseline,(result.returncode,result.stderr)
        fault_restore()
        report=dict(returncode=1,stderr=result.stderr,phase='refused-before-config-write')
    else:
        prepared=call(shell,os.environ,'brl_web_config_prepare')
        assert prepared.returncode==0,prepared.stderr
        planned=json.loads(journal.read_text())['webConfig']
        assert planned['oldConfig'].encode()==config_bytes and planned['oldOwner'].encode()==owner_bytes
        expected=config_bytes.replace(b'"/opt/broray-light/run/lighttpd.pid"',b'"/tmp/broray-light/run/lighttpd.pid"').replace(b'"/opt/broray-light/logs/lighttpd-error.log"',b'"/tmp/broray-light/logs/lighttpd-error.log"')
        assert planned['newConfig'].encode()==expected,'Unrelated config/auth setting changed'
        if mode.startswith('partial-'):
            name=mode.split('-')[1]
            part=call(shell,os.environ,'brl_web_config_bound && brl_web_config_targets_valid mixed && brl_web_config_write '+name+' new')
            assert part.returncode==0,part.stderr
        elif mode.startswith('staged-'):
            name=mode.split('-')[1]
            target=config if name=='Config' else owner
            stage=target.with_name('.'+target.name+'.r0013-installed')
            stage.write_bytes(b'partial-owned-config\n');stage.chmod(0o600)
            value=json.loads(journal.read_text());st=stage.stat()
            value['webConfig']['staged']={name:dict(inode=f'{st.st_dev}:{st.st_ino}')}
            journal.write_text(json.dumps(value))
        elif mode=='foreign-stage':
            stage=owner.with_name('.'+owner.name+'.r0013-installed')
            stage.write_bytes(b'foreign\n');stage.chmod(0o600)
            baseline=inventory(root)
            refused=call(shell,os.environ,'brl_web_config_activate')
            assert refused.returncode==1 and inventory(root)==baseline,(refused.returncode,refused.stderr)
            stage.unlink() # Fixture owns the deliberately injected foreign object.
        if not mode.endswith('-rollback'):
            activated=call(shell,os.environ,'brl_web_config_activate')
            assert activated.returncode==0,activated.stderr
            assert config.read_bytes()==expected and config.stat().st_mode&0o777==0o600
            new_owner=json.loads(owner.read_bytes());old_owner=json.loads(owner_bytes)
            old_owner['lighttpdConfigSha256']=hashlib.sha256(expected).hexdigest()
            assert new_owner==old_owner,'Unrelated owner/policy fields changed'
            baseline=inventory(root)
            again=call(shell,os.environ,'brl_web_config_activate')
            assert again.returncode==0 and inventory(root)==baseline,again.stderr
        restored=call(shell,os.environ,'brl_web_config_restore')
        assert restored.returncode==0,restored.stderr
        assert config.read_bytes()==config_bytes and owner.read_bytes()==owner_bytes
        assert config.stat().st_mode&0o777==config_mode and owner.stat().st_mode&0o777==0o600
        assert not list(config.parent.glob('*.r0013-installed'))
        baseline=inventory(root)
        again=call(shell,os.environ,'brl_web_config_restore')
        assert again.returncode==0 and inventory(root)==baseline,again.stderr
        report=dict(returncode=0,stderr='',phase='exact-config-and-receipt-restored')
    restored_ram=call(shell,os.environ,'brl_r1_ram_restore')
    assert restored_ram.returncode==0,restored_ram.stderr
    (root/'admission-result.json').write_text(json.dumps(report))
    return 1


class WebFixture(PlatformFixture):
    def __init__(self,shell,mode):
        super().__init__(shell,'valid')
        config=self.app/'config/lighttpd.conf'
        payload=git_bytes('packaging/app-overlay/share/defaults/lighttpd.conf')
        self.write(config,payload,0o644)
        receipt=dict(schemaVersion=1,owner='BROray-Light',name='brolight',policySha256=POLICY_SHA,
                     lighttpdConfigSha256=hashlib.sha256(payload).hexdigest(),upstreamHost='192.0.2.1',upstreamPort=8080)
        self.write(config.with_name('web-publish.json'),(json.dumps(receipt,indent=2)+'\n').encode(),0o600)
        command=' '.join(shlex.quote(x) for x in [sys.executable,'-B',str(Path(__file__).resolve()),'--callback',mode])
        hook='''#!/bin/sh
if [ "$1" = start ] && [ "$(readlink "$2/current")" = releases/2.0.0-r1 ]; then
 exec CALLBACK
fi
exit 0
'''.replace('CALLBACK',command)
        self.write(self.executable/'service',hook.encode(),0o755)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--shell',default='/bin/dash')
    parser.add_argument('--busybox',action='store_true')
    parser.add_argument('--busybox-tools',action='store_true')
    parser.add_argument('--result',type=Path)
    parser.add_argument('--callback')
    args=parser.parse_args()
    if args.callback:raise SystemExit(callback(args.callback))
    assert os.geteuid()==0
    shell=[args.shell,'ash'] if args.busybox else [args.shell]
    if args.busybox_tools:
        import r0013_busybox_fixture
        utility_fixture=r0013_busybox_fixture.enable()
    records=[];failed=False
    modes=['activate-restore','missing-owner','owner-sha-mismatch','duplicate-pid-directive','config-symlink','foreign-stage']
    modes += [f'{kind}-{name}-{direction}' for kind in ('partial','staged') for name in ('Config','Owner') for direction in ('resume','rollback')]
    for mode in modes:
        fixture=None
        try:
            fixture=WebFixture(shell,mode)
            before=fixture.persistent()
            result=fixture.update(1)
            assert fixture.current()=='1.0.0-r1' and fixture.persistent()==before
            records.append(dict(name=mode,status='PASS',callback=result))
        except Exception as error:
            records.append(dict(name=mode,status='FAIL',error=str(error)));failed=True;break
        finally:
            if fixture:fixture.close()
    report=dict(stage='R0013',revision='p35-web-config-and-ownership-receipt-transaction',
                status='FAIL_FIRST_ERROR' if failed else 'PASS_CONFIG_AND_RECEIPT_TRANSACTION',
                scope='Real r1 updater, exact config/receipt bytes and journaled pair replacement; service boundary mocked',
                sourceSha256=hashlib.sha256(WEB.read_bytes()).hexdigest(),shell=shell,
                utilities='BusyBox applets' if args.busybox_tools else 'host utilities',tests=records)
    payload=(json.dumps(report,indent=2)+'\n').encode()
    if args.result:
        args.result.parent.mkdir(parents=True,exist_ok=True);args.result.write_bytes(payload)
    print(payload.decode())
    if args.busybox_tools:utility_fixture.cleanup()
    raise SystemExit(1 if failed else 0)


if __name__=='__main__':main()
