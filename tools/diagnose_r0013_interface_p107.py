"""Compare uncached snapshot and direct library, read-only on test target."""
import json
from diagnose_r0013_xray_compatibility import Target, REPO
p=REPO/'checkpoints/R0013/INTERFACE-UNCACHED-P107.json';assert not p.exists()
r={'revision':'p107-readonly-uncached-comparison','status':'IN_PROGRESS','observations':[],'candidateReady':False}
def save():p.write_bytes((json.dumps(r,ensure_ascii=False,indent=2)+'\n').encode())
save();t=Target()
try:
  for name,cmd in [
    ('direct-actual-library',"/opt/bin/ash -c '. /opt/broray-light/lib/runtime-environment.sh; . /opt/broray-light/lib/keenetic-page.sh; broray_keenetic_read_actual_json'"),
    ('direct-full-health-library',"/opt/bin/ash -c '. /opt/broray-light/lib/runtime-environment.sh; . /opt/broray-light/lib/keenetic-page.sh; broray_keenetic_status_json' | jq '{actual,health}'"),
    ('uncached-home-snapshot',"BRORAY_KEENETIC_STATUS_CACHE_SECONDS=0 /opt/broray-light/bin/broray-home-snapshot | jq '{generatedAt,keenetic:{actual:.keenetic.actual,health:.keenetic.health}}'")
  ]:
    v=t.command(cmd,timeout=50,check=False);r['observations'].append({'name':name,**v});save();print(json.dumps({'name':name,**v},ensure_ascii=False),flush=True)
  r['status']='DIAGNOSTIC_COMPLETE'
finally:save();t.client.close()
