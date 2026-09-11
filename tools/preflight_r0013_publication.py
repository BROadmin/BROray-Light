"""Read-only release and website publication preflight."""
import base64,hashlib,json,urllib.error
from prepare_r0013_release_assets import GitHub, ROOT
p=ROOT/'checkpoints/R0013/PUBLICATION-PREFLIGHT-P115.json';assert not p.exists()
g=GitHub();rows=[]
for repo in ('BROray-Light','BROray'):
 d=g.request('/repos/BROadmin/'+repo)
 assert d['default_branch']=='main' and d['permissions']['push'] is True
 rows.append({'repository':repo,'defaultBranch':d['default_branch'],'pushAllowed':True})
base='/repos/BROadmin/BROray';head=g.request(base+'/git/ref/heads/main')['object']['sha']
files=[]
for name in ('index.html','styles.css','broray-light/index.html'):
 d=g.request(base+'/contents/site/docs.brovibe.cloud/'+name+'?ref='+head)
 body=base64.b64decode(d['content']);local=(ROOT/'publication/R0013/templates'/name).read_bytes()
 files.append({'path':name,'gitBlob':d['sha'],'sha256':hashlib.sha256(body).hexdigest(),'matchesReviewedTemplate':body==local})
base='/repos/BROadmin/BROray-Light'
for endpoint in ('/git/ref/tags/v2.0.0','/releases/tags/v2.0.0'):
 try:g.request(base+endpoint)
 except urllib.error.HTTPError as e:assert e.code==404
 else:raise AssertionError('Immutable publication target already exists')
r={'schemaVersion':1,'revision':'p115-readonly-publication-preflight','status':'PASS' if all(x['matchesReviewedTemplate'] for x in files) else 'FAIL_SOURCE_CHANGED','repositories':rows,'websiteSourceCommit':head,'websiteTemplates':files,'tagAbsent':True,'releaseAbsent':True,'publicReleasePublished':False,'candidateReady':False}
p.write_bytes((json.dumps(r,indent=2)+'\n').encode());print(json.dumps(r,indent=2))
assert r['status']=='PASS'
