"""Exact signed-index decisions, service restart and persistence on authorized target."""
import json,re
from diagnose_r0013_xray_compatibility import Target, REPO

P=REPO/'checkpoints/R0013/TARGET-FINAL-P113.json';assert not P.exists()
R={'schemaVersion':1,'revision':'p113-final-target-lifecycle-v1','status':'IN_PROGRESS','candidateReady':False,'sourceCommit':'f4af30d98fd1f227e5116def825c09399437086f','tests':[]}
def save():P.write_bytes((json.dumps(R,ensure_ascii=False,indent=2)+'\n').encode())
save();t=Target()
def run(name,script,expected=0,timeout=55):
    v=t.command('set -eu; umask 077\n'+script,timeout=timeout,check=False)
    R['tests'].append({'name':name,'status':'PASS' if v['exitCode']==expected else 'FAIL',**v});save()
    assert v['exitCode']==expected,'STOP '+name
    print(name+': PASS',flush=True);return v['stdout']
try:
    w=run('final-slot-and-daemon-tmpdir', '''
test "$(sha256sum /opt/broray-light/current/APP-SHA256SUMS | awk '{print $1}')" = 52ac9892e65fe86faf0a2432299a6e1becda23e1a93678a6ca1b778c78cb8a3c
(cd /opt/broray-light/current && sha256sum -c APP-SHA256SUMS >/dev/null)
pid=$(cat /tmp/broray-light/run/broray-lightd.pid)
case "$pid" in ''|*[!0-9]*) exit 1;; esac
tr '\\000' '\\n' </proc/$pid/environ | grep -Fx 'TMPDIR=/tmp/broray-light/tmp' >/dev/null
test "$(stat -c %u:%a /tmp/broray-light/tmp)" = 0:700
test "$(stat -f -c %T /tmp)" = tmpfs
mktemp -d /tmp/brl-final-audit-p113.XXXXXX
''').strip()
    assert re.fullmatch(r'/tmp/brl-final-audit-p113\.[A-Za-z0-9]{6}',w)
    R['protectedRamPath']=w;save()
    run('snapshot-durable-before',f'find /opt/broray-light/config /opt/broray-light/servers /opt/broray-light/subscriptions /opt/broray-light/runtime -type f -exec sha256sum {{}} + | sort >{w}/durable.sha256\nsha256sum {w}/durable.sha256')
    index='https://raw.githubusercontent.com/BROadmin/BROray-Light/3af7a7c28b3703f6ea8f3470012d053fdcc34b37/checkpoints/R0013/signed-probe-p112/release.json'
    updater='/opt/libexec/broray-light-updater/broray-light-updater.sh'
    command='BRORAY_LIGHT_RELEASE_INDEX_URL='+index+' '+updater
    raw=run('existing-key-signed-index-check',command+' check')
    d=json.loads(raw);assert d['relation']=='equal' and d['installedReleaseId']=='2.0.0-r1' and d['updateAvailable'] is False
    raw=run('same-version-signed-updater-noop',command+' update')
    assert json.loads(raw)['relation']=='equal'
    run('immutable-r1-downgrade-refusal','BRORAY_LIGHT_RELEASE_INDEX_URL=https://github.com/BROadmin/BROray-Light/releases/download/v1.0.0-r1/release.json '+updater+' update',expected=20)
    run('restart-both-owned-services','''
/opt/etc/init.d/S24broray-light stop
/opt/etc/init.d/S23broray-light-updater stop
/opt/etc/init.d/S23broray-light-updater start
/opt/etc/init.d/S24broray-light start
/opt/etc/init.d/S23broray-light-updater status
/opt/etc/init.d/S24broray-light status
''',timeout=110)
    run('post-restart-exact-durable-persistence',f'sha256sum -c {w}/durable.sha256 >/dev/null')
    run('native-interface-owner-and-runtime-health',"/opt/bin/ash -c '. /opt/broray-light/lib/runtime-environment.sh; . /opt/broray-light/lib/interface-core.sh; broray_interface_check'")
    run('post-restart-snapshot-health',"BRORAY_KEENETIC_STATUS_CACHE_SECONDS=0 /opt/broray-light/bin/broray-home-snapshot | jq -e '.keenetic.health.severity==\"ok\" and .keenetic.health.operational==true and .keenetic.health.facts.ownershipConfirmed==true and .connection.connected==true'",timeout=35)
    run('audit-scratch-cleanup',f'test ! -L {w}; test "$(stat -c %u:%a {w})" = 0:700; test -f {w}/durable.sha256; rm {w}/durable.sha256; rmdir {w}; test ! -e {w}')
    R['status']='PASS_SIGNED_CHECK_EQUAL_DOWNGRADE_RESTART_PERSISTENCE_HEALTH'
except Exception as e:
    R.update(status='FAIL_FIRST_ERROR',error=str(e)[:200],nextExactAction='READ_EXACT_FAILURE_NO_HIDDEN_RETRY');raise
finally:save();t.client.close()
