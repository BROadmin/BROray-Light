"""Single read-only comparison of native CLI and snapshot environments."""
import json
from diagnose_r0013_xray_compatibility import Target, REPO
path=REPO/'checkpoints/R0013/INTERFACE-ENVIRONMENT-P106.json'
assert not path.exists()
r={'schemaVersion':1,'revision':'p106-readonly-snapshot-environment','status':'IN_PROGRESS','observations':[],'candidateReady':False}
def save():path.write_bytes((json.dumps(r,ensure_ascii=False,indent=2)+'\n').encode())
save();t=Target()
try:
    commands=[
      ('prepared-read-values',"/opt/bin/ash -c '. /opt/broray-light/lib/runtime-environment.sh; . /opt/broray-light/lib/interface-core.sh; for f in type description link connected state; do printf \"%s=\" \"$f\"; broray_interface_value \"$f\"; printf \"rc=%s\\n\" \"$?\"; done'"),
      ('home-snapshot-once',"/opt/broray-light/bin/broray-home-snapshot | jq '{generatedAt,keenetic:{healthy:.keenetic.healthy,actual:.keenetic.actual,health:.keenetic.health}}'"),
      ('prepared-path-and-ram',"sed -n '1,120p' /opt/broray-light/lib/runtime-environment.sh; stat -c '%u:%a %n' /tmp/broray-light/tmp /tmp/broray-light/run; sed -n '1,120p' /opt/broray-light/bin/broray-lightd"),
      ('core-functions-through-null-stdin',"/opt/bin/ash -c '. /opt/broray-light/lib/runtime-environment.sh; . /opt/broray-light/lib/interface-core.sh; broray_interface_value type; broray_interface_check' </dev/null")
    ]
    for name,command in commands:
      v=t.command(command,timeout=50,check=False);r['observations'].append({'name':name,**v});save();print(json.dumps({'name':name,**v},ensure_ascii=False),flush=True)
    r['status']='DIAGNOSTIC_COMPLETE_NO_CONFIGURATION_MUTATION'
finally:save();t.client.close()
