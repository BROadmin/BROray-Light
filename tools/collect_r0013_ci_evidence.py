"""Collect successful exact-source CI receipts, preserving artifact digest binding."""
import argparse,hashlib,io,json,zipfile
from pathlib import PurePosixPath
from prepare_r0013_release_assets import GitHub, ROOT
p=argparse.ArgumentParser();p.add_argument('--run',required=True,type=int);p.add_argument('--source',required=True);p.add_argument('--stage',required=True);a=p.parse_args()
out=ROOT/('dist/R0013/'+a.stage.lower()+'-ci');receipt=ROOT/('checkpoints/R0013/'+a.stage+'.json')
assert not out.exists() and not receipt.exists()
g=GitHub();base='/repos/BROadmin/BROray-Light/actions/runs/'+str(a.run)
run=g.request(base);assert run['head_sha']==a.source and run['conclusion']=='success'
jobs=g.request(base+'/jobs')['jobs'];assert jobs and all(j['conclusion']=='success' for j in jobs)
items=g.request(base+'/artifacts')['artifacts'];assert items
out.mkdir();rows=[];reports=[]
for item in items:
  body=g.artifact(item);(out/(str(item['id'])+'.zip')).write_bytes(body)
  rows.append({'name':item['name'],'id':item['id'],'zipSha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)})
  with zipfile.ZipFile(io.BytesIO(body)) as z:
    for member in z.infolist():
      name=PurePosixPath(member.filename)
      assert not name.is_absolute() and '..' not in name.parts and '\\' not in member.filename and member.file_size<20*1024*1024
      if member.is_dir() or not member.filename.endswith('.json'):continue
      raw=z.read(member);obj=json.loads(raw)
      if not isinstance(obj,dict) or not isinstance(obj.get('tests'),list):continue
      tests=obj['tests']
      assert not any(isinstance(t,dict) and t.get('status')=='FAIL' for t in tests),member.filename
      reports.append({'artifactId':item['id'],'name':member.filename,'sha256':hashlib.sha256(raw).hexdigest(),'status':obj.get('status'),'testCount':len(tests),'tests':[{'name':t.get('name',t.get('test')),'status':t.get('status')} for t in tests if isinstance(t,dict)]})
r={'schemaVersion':1,'revision':a.stage.lower(),'status':'PASS_EXACT_SOURCE_CI','sourceCommit':a.source,'runId':a.run,'url':run['html_url'],'jobs':[{'id':j['id'],'name':j['name'],'conclusion':j['conclusion']} for j in jobs],'artifacts':rows,'reports':reports,'testInvocations':sum(x['testCount'] for x in reports),'candidateReady':False}
receipt.write_bytes((json.dumps(r,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'status':r['status'],'jobs':len(jobs),'reports':len(reports),'testInvocations':r['testInvocations'],'receipt':receipt.relative_to(ROOT).as_posix()}))
