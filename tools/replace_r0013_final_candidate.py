"""Authorized exact P97 test-target package replacement; no remote retries."""
import base64
import argparse
import hashlib
import json
from pathlib import Path
import re
from diagnose_r0013_xray_compatibility import Target, REPO

parser=argparse.ArgumentParser()
parser.add_argument('--stage',required=True)
parser.add_argument('--build',required=True)
parser.add_argument('--old',required=True)
parser.add_argument('--build-receipt',required=True)
args=parser.parse_args()
assert re.fullmatch(r'P[0-9]+',args.stage)
BUILD = (REPO / args.build).resolve()
OLD = (REPO / args.old).resolve()
assert BUILD.is_relative_to(REPO/'dist/R0013') and OLD.is_relative_to(REPO/'dist/R0013')
receipt=json.loads((REPO/args.build_receipt).read_bytes())
assert receipt['status']=='PASS_EXACT_AB_AND_SIGNED_INDEX_BINDING'
for item in receipt['artifacts']:
    assert hashlib.sha256((BUILD/item['name']).read_bytes()).hexdigest()==item['sha256']
new_manifest=json.loads((BUILD/'ENGINEERING-MANIFEST.json').read_bytes())['slot']['appSha256SumsSha256']
old_manifest=json.loads((OLD/'ENGINEERING-MANIFEST.json').read_bytes())['slot']['appSha256SumsSha256']
ram_prefix='/tmp/brl-r13-final-'+args.stage.lower()+'.'
OUT = REPO / ('dist/R0013/private-target/'+args.stage.lower())
REPORT = REPO / ('checkpoints/R0013/TARGET-INSTALL-'+args.stage+'.json')
assert not OUT.exists() and not REPORT.exists()
OUT.mkdir()
report = {'schemaVersion':1,'revision':args.stage.lower()+'-final-package-v1','status':'IN_PROGRESS','sourceCommit':receipt['sourceCommit'],'candidateReady':False,'steps':[]}
REPORT.write_bytes((json.dumps(report,indent=2)+'\n').encode())
target = Target()


def save():
    REPORT.write_bytes((json.dumps(report,indent=2)+'\n').encode())


def step(name, script, timeout=60):
    result = target.command('set -eu; umask 077\n'+script, timeout=timeout, check=False)
    report['steps'].append({'name':name,'exitCode':result['exitCode'],'stdout':result['stdout'],'stderr':result['stderr']})
    save()
    assert result['exitCode'] == 0, 'STOP '+name
    print(name+': PASS',flush=True)
    return result['stdout']


try:
    work = step('preflight', '''
test "$(stat -f -c %T /tmp)" = tmpfs
test "$(df -k /tmp | awk 'END{print $4}')" -gt 120000
test "$(readlink /opt/broray-light/current)" = releases/2.0.0-r1
test "$(sha256sum /opt/broray-light/current/APP-SHA256SUMS | awk '{print $1}')" = @OLD_MANIFEST@
(cd /opt/broray-light/current && sha256sum -c APP-SHA256SUMS >/dev/null)
test ! -e /opt/broray
test ! -e /opt/etc/init.d/S24broray
mktemp -d @RAM_PREFIX@XXXXXX
'''.replace('@OLD_MANIFEST@',old_manifest).replace('@RAM_PREFIX@',ram_prefix)).strip()
    assert re.fullmatch(re.escape(ram_prefix)+r'[A-Za-z0-9]{6}',work)
    target.work=work
    report['protectedRamPath']=work
    for folder, prefix in ((BUILD,'new'),(OLD,'rollback')):
        for source_name, output_name in (('broray-light-install-2.0.0.sh',prefix+'-installer.sh'),('broray-light_2.0.0_aarch64-3.10.ipk',prefix+'-package.ipk')):
            body=(folder/source_name).read_bytes()
            target.put(output_name,body)
            report.setdefault('inputs',[]).append({'name':output_name,'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)})
            save()
    step('fresh-private-backup', f'''
test "$(stat -c %u:%a {work})" = 0:700
find /opt/broray-light/config /opt/broray-light/servers /opt/broray-light/subscriptions /opt/broray-light/runtime -type f -exec sha256sum '{{}}' + | sort >{work}/durable-before.sha256
tar -czf {work}/private-before.tar.gz -C / opt/broray-light/config opt/broray-light/servers opt/broray-light/subscriptions opt/broray-light/runtime opt/var/lib/broray-light opt/var/lib/broray-light-updater
gzip -t {work}/private-before.tar.gz
''')
    raw=base64.b64decode(target.command('base64 '+work+'/private-before.tar.gz',timeout=90)['stdout'])
    expected=target.command('sha256sum '+work+'/private-before.tar.gz')['stdout'].split()[0]
    assert hashlib.sha256(raw).hexdigest()==expected
    (OUT/'private-before.tar.gz').write_bytes(raw)
    report['privateBackup']={'path':(OUT/'private-before.tar.gz').relative_to(REPO).as_posix(),'sha256':expected,'bytes':len(raw)}
    save()
    step('stop-owned-services', '''
/opt/etc/init.d/S24broray-light stop
/opt/etc/init.d/S23broray-light-updater stop
for proc in /proc/[0-9]*/exe; do
 test -L "$proc" || continue
 case "$(readlink "$proc")" in /opt/broray-light/*|/tmp/broray-light/run/web-new/native-auth/*) echo 'Owned executable remains'; exit 1;; esac
done
''',timeout=90)
    step('official-package-removal-retaining-durable-state', f'''
mkdir {work}/opkg-remove
TMPDIR={work}/opkg-remove opkg --tmp-dir {work}/opkg-remove remove broray-light
test -z "$(opkg status broray-light)"
test -L /opt/broray-light/current
test "$(readlink /opt/broray-light/current)" = releases/2.0.0-r1
test ! -e /opt/broray-light/current/app/lib/runtime-environment.sh
rm /opt/broray-light/current
''')
    step('install-exact-final-package', f'BRORAY_LIGHT_PACKAGE_FILE={work}/new-package.ipk /opt/bin/ash {work}/new-installer.sh', timeout=150)
    step('verify-slot-runtime-and-services', '''
test "$(sha256sum /opt/broray-light/current/APP-SHA256SUMS | awk '{print $1}')" = @NEW_MANIFEST@
(cd /opt/broray-light/current && sha256sum -c APP-SHA256SUMS >/dev/null)
test "$(sha256sum /opt/broray-light/runtime/xray | awk '{print $1}')" = c1defe42b6db958a97c5e049a02a00a4baaedaca7b51c1c229f0830e288acef5
/opt/etc/init.d/S24broray-light status
/opt/etc/init.d/S23broray-light-updater status
jq -e '.schemaVersion==1 and (.identity|length)==6' /opt/broray-light/config/system/server-canonical-owners.json >/dev/null
'''.replace('@NEW_MANIFEST@',new_manifest))
    step('verify-existing-durable-file-bytes', f'sha256sum -c {work}/durable-before.sha256 >/dev/null')
    report['status']='PASS_EXACT_CANDIDATE_INSTALLED_EXISTING_DURABLE_FILES_PRESERVED'
    report['newDurableFile']='config/system/server-canonical-owners.json'
    # Keep checked rollback inputs in protected RAM until target acceptance;
    # cleanup is a separate explicit stage, never a broad fallback delete.
    report['nextExactAction']='NATIVE_BROWSER_NEGATIVE_REGISTRY_OVERLAP_RESTART_SIGNED_UPDATER_AND_EXACT_RAM_CLEANUP'
except Exception as error:
    report.update(status='FAIL_FIRST_ERROR',errorType=type(error).__name__,error=str(error)[:300],nextExactAction='INSPECT_FIRST_FAILURE_AND_USE_VERIFIED_ROLLBACK_INPUTS_IF_REQUIRED_NO_HIDDEN_RETRY')
    raise
finally:
    save();target.client.close()
print(json.dumps({'status':report['status'],'checkpoint':str(REPORT.relative_to(REPO))}))
