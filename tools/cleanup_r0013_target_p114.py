"""Delete only verified P100/P110 test inputs, after durable backup verification."""
import hashlib,json,re
from diagnose_r0013_xray_compatibility import Target, REPO
p=REPO/'checkpoints/R0013/TARGET-CLEANUP-P114-V2.json';assert not p.exists()
final=json.loads((REPO/'checkpoints/R0013/TARGET-FINAL-P113.json').read_bytes())
assert final['status']=='PASS_SIGNED_CHECK_EQUAL_DOWNGRADE_RESTART_PERSISTENCE_HEALTH'
records=[]
for stage in ('P100','P110'):
 r=json.loads((REPO/('checkpoints/R0013/TARGET-INSTALL-'+stage+'.json')).read_bytes());w=r['protectedRamPath']
 assert re.fullmatch('/tmp/brl-r13-final-'+stage.lower()+r'\.[A-Za-z0-9]{6}',w)
 backup=r['privateBackup'];assert hashlib.sha256((REPO/backup['path']).read_bytes()).hexdigest()==backup['sha256']
 records.append((stage,w,r))
report={'revision':'p114-v2-cleanup-script-on-stdin','status':'IN_PROGRESS','candidateReady':False,'directories':[]}
def save():p.write_bytes((json.dumps(report,indent=2)+'\n').encode())
save();t=Target()
try:
 for stage,w,r in records:
  # Check every input before deleting anything. No recursive deletion.
  script=f'''set -eu
test ! -L {w}; test "$(stat -c %u:%a {w})" = 0:700
test -d {w}/opkg-remove; test ! -L {w}/opkg-remove
test -z "$(find {w}/opkg-remove -mindepth 1 -print)"
test "$(find {w} -mindepth 1 -maxdepth 1 | wc -l)" -eq 7
for proc in /proc/[0-9]*/cmdline; do
 test -r "$proc" || continue
 if tr '\\000' '\\n' <"$proc" | grep -F '{w}/' >/dev/null; then exit 71; fi
done
'''
  for item in r['inputs']+[{'name':'private-before.tar.gz','sha256':r['privateBackup']['sha256']}]:
   script+=f"test -f {w}/{item['name']}; test ! -L {w}/{item['name']}\ntest \"$(sha256sum {w}/{item['name']} | awk '{{print $1}}')\" = {item['sha256']}\n"
  script+=f'test -f {w}/durable-before.sha256; test ! -L {w}/durable-before.sha256\n'
  script+=f"rm {w}/new-installer.sh {w}/new-package.ipk {w}/rollback-installer.sh {w}/rollback-package.ipk {w}/private-before.tar.gz {w}/durable-before.sha256\nrmdir {w}/opkg-remove\nrmdir {w}\ntest ! -e {w}\n"
  v=t.command('/opt/bin/ash -s',payload=script.encode(),timeout=30,check=False);report['directories'].append({'stage':stage,'path':w,**v});save();assert v['exitCode']==0,'Stop cleanup '+stage
 report.update(status='PASS_EXACT_INPUTS_REMOVED_PRIVATE_BACKUPS_RETAINED',localPrivateBackupsRetained=True)
finally:save();t.client.close()
print(json.dumps({'status':report['status'],'directories':2}))
