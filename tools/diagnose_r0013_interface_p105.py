"""Bounded read-only diagnostic of the exact authorized test interface."""
import json
from diagnose_r0013_xray_compatibility import Target, REPO

path=REPO/'checkpoints/R0013/INTERFACE-DIAGNOSIS-P105.json'
assert not path.exists()
report={'schemaVersion':1,'revision':'p105-readonly-interface-diagnosis','status':'IN_PROGRESS','candidateReady':False,'observations':[]}
def save(): path.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode())
save()
t=Target()
try:
    for name,command in [
        ('native-show-proxy0',"ndmc -c 'show interface Proxy0'"),
        ('prepared-cli-interface-read',"/opt/broray-light/bin/broray interface check"),
        ('prepared-read-environment',"printf 'run='; readlink /opt/broray-light/run; printf 'tmp='; readlink /opt/broray-light/tmp; /opt/bin/ash -c '. /opt/broray-light/lib/runtime-environment.sh; env | sort | sed -n /BRORAY_INTERFACE/p'"),
        ('isolated-interface-output-once',"/opt/bin/ash -c '. /opt/broray-light/lib/runtime-environment.sh; . /opt/broray-light/lib/interface-core.sh; broray_interface_output'"),
        ('owned-interface-health',"/opt/bin/ash -c '. /opt/broray-light/lib/runtime-environment.sh; . /opt/broray-light/lib/interface-core.sh; broray_interface_check'"),
    ]:
        result=t.command(command,timeout=45,check=False)
        report['observations'].append({'name':name,**result});save()
        print(json.dumps({'name':name,**result},ensure_ascii=False),flush=True)
    report['status']='DIAGNOSTIC_COMPLETE_NO_MUTATION'
finally:
    save(); t.client.close()
