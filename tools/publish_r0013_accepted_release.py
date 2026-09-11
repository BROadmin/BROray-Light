"""Publish only a fully accepted immutable release; no retry, overwrite or key access."""
import argparse,hashlib,json,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from prepare_r0013_release_assets import GitHub, ROOT

def sha(body):return hashlib.sha256(body).hexdigest()
def dump(path,value):path.write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode())

def main():
 p=argparse.ArgumentParser();p.add_argument('--acceptance',required=True);p.add_argument('--commit',required=True);a=p.parse_args()
 receipt=ROOT/'checkpoints/R0013/RELEASE-PUBLISH-P116.json'
 assert not receipt.exists(),'No implicit retry'
 acceptance_path=ROOT/a.acceptance;acceptance=json.loads(acceptance_path.read_bytes())
 assert acceptance['candidateReady'] is True and acceptance['releaseReady'] is True
 assert acceptance['sourceCommit']=='f4af30d98fd1f227e5116def825c09399437086f'
 assert acceptance['gates'] and all(x['status']=='PASS' for x in acceptance['gates'])
 for row in acceptance['evidence']:
  assert sha((ROOT/row['path']).read_bytes())==row['sha256'],row['path']
 out=ROOT/'dist/R0013/public-v2.0.0';assert not out.exists();out.mkdir()
 build=ROOT/'dist/R0013/p109-release-build/A';signed=build.parent/'signed'
 artifacts={}
 for name in ('broray-light-app-2.0.0-r1.tar.gz','broray-light_2.0.0_aarch64-3.10.ipk','broray-light-install-2.0.0.sh','broray-light-updater-platform-5-light2-ram.tar.gz','INPUT-MANIFEST.json'):
  artifacts[name]=(build/name).read_bytes()
 for name in ('release.json','release.json.minisig'):artifacts[name]=(signed/name).read_bytes()
 artifacts['REPRODUCIBILITY.json']=(ROOT/'checkpoints/R0013/INDEPENDENT-BUILDS-P109.json').read_bytes()
 artifacts['ACCEPTANCE.json']=acceptance_path.read_bytes()
 engineering=json.loads((build/'ENGINEERING-MANIFEST.json').read_bytes())
 manifest={'schemaVersion':1,'product':'BROray-Light','version':'2.0.0','releaseId':'2.0.0-r1','tag':'v2.0.0','sourceCommit':acceptance['sourceCommit'],'releaseCommit':a.commit,'candidateReady':True,'releaseReady':True,'slot':engineering['slot'],'xray':engineering['xray'],'acceptanceSha256':sha(artifacts['ACCEPTANCE.json']),'artifacts':[{'name':n,'bytes':len(b),'sha256':sha(b)} for n,b in sorted(artifacts.items())]}
 artifacts['RELEASE-MANIFEST.json']=(json.dumps(manifest,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode()
 artifacts['SHA256SUMS']=''.join(sha(b)+'  '+n+'\n' for n,b in sorted(artifacts.items())).encode()
 for n,b in artifacts.items():(out/n).write_bytes(b)
 g=GitHub();base='/repos/BROadmin/BROray-Light';r={'schemaVersion':1,'revision':'p116-immutable-release-publication-v1','status':'PREFLIGHT','releaseCommit':a.commit,'sourceCommit':acceptance['sourceCommit'],'publicReleasePublished':False,'steps':[]}
 def save():dump(receipt,r)
 def absent(path):
  try:g.request(base+path)
  except urllib.error.HTTPError as e:
   assert e.code==404;return
  raise AssertionError('Existing immutable target refused: '+path)
 def download(url,authenticated=False):
  headers={'User-Agent':'BROray-Light-public-byte-validation'}
  if authenticated:headers.update(Authorization='Bearer '+g.token,Accept='application/octet-stream')
  req=urllib.request.Request(url,headers=headers)
  try:response=g.opener.open(req,timeout=45)
  except urllib.error.HTTPError as e:
   assert e.code==302 and e.headers['Location'].startswith('https://')
   response=urllib.request.urlopen(urllib.request.Request(e.headers['Location'],headers={'User-Agent':headers['User-Agent']}),timeout=45)
  with response:
   assert response.url.startswith('https://');body=response.read(30*1024*1024+1)
   assert len(body)<=30*1024*1024
   return body,{'finalUrlHost':urllib.parse.urlparse(response.url).hostname,'contentType':response.headers.get('Content-Type'),'status':response.status}
 save()
 try:
  assert g.request(base+'/git/ref/heads/codex/r0009-updater-package')['object']['sha']==a.commit
  absent('/git/ref/tags/v2.0.0');absent('/releases/tags/v2.0.0')
  previous=g.request(base+'/releases/latest');r['previousLatest']={k:previous[k] for k in ('id','tag_name','target_commitish')}
  r['previousAssets']=[{'id':x['id'],'name':x['name'],'size':x['size'],'digest':x.get('digest')} for x in previous['assets']];save()
  tag=g.request(base+'/git/refs',{'ref':'refs/tags/v2.0.0','sha':a.commit});assert tag['object']['sha']==a.commit
  r['steps'].append({'name':'immutable-tag-created','status':'PASS'});save()
  body=(ROOT/'publication/R0013/github/release-notes.md').read_text(encoding='utf-8')
  release=g.request(base+'/releases',{'tag_name':'v2.0.0','target_commitish':a.commit,'name':'BROray-Light 2.0.0','body':body,'draft':True,'prerelease':False,'make_latest':'false'})
  r['releaseId']=release['id'];r['releaseUrl']=release['html_url'];r['status']='DRAFT_CREATED';save()
  uploaded=[]
  for name,content in sorted(artifacts.items()):
   url=release['upload_url'].split('{',1)[0]+'?name='+urllib.parse.quote(name)
   assert urllib.parse.urlparse(url).hostname=='uploads.github.com'
   req=urllib.request.Request(url,data=content,method='POST',headers={'Authorization':'Bearer '+g.token,'Content-Type':'application/octet-stream','User-Agent':'BROray-Light-release-publication'})
   with g.opener.open(req,timeout=90) as response:item=json.load(response)
   assert item['state']=='uploaded' and item['size']==len(content)
   assert item.get('digest')=='sha256:'+sha(content)
   downloaded,headers=download(item['url'],True);assert downloaded==content,'Draft asset mismatch '+name
   row={'id':item['id'],'name':name,'bytes':len(content),'sha256':sha(content),'url':item['browser_download_url'],'draftBytesVerified':True}
   uploaded.append(row);r['assets']=uploaded;save();print('Verified draft asset: '+name,flush=True)
  published=g.request(base+'/releases/'+str(release['id']),{'draft':False,'prerelease':False,'make_latest':'true'},method='PATCH')
  assert published['draft'] is False and published['prerelease'] is False
  r['publicReleasePublished']=True;r['publishedAt']=published['published_at'];r['status']='PUBLISHED_PUBLIC_BYTES_PENDING';save()
  for row in uploaded:
   body,headers=download(row['url']);assert sha(body)==row['sha256'] and len(body)==row['bytes']
   row['publicBytesVerified']=True;row['publicResponse']=headers;save()
  latest=g.request(base+'/releases/latest');assert latest['id']==release['id'] and latest['tag_name']=='v2.0.0'
  old=g.request(base+'/releases/'+str(previous['id']))
  assert [{'id':x['id'],'name':x['name'],'size':x['size'],'digest':x.get('digest')} for x in old['assets']]==r['previousAssets']
  r.update(status='PASS_PUBLISHED_IMMUTABLE_RELEASE_AND_PUBLIC_BYTES',latestVerified=True,previousAssetsPreserved=True);save()
 except Exception as error:
  r.update(status='FAIL_FIRST_ERROR',errorType=type(error).__name__,error=str(error)[:300]);save()
  failure=ROOT/'checkpoints/R0013/process-failures/FAILURE-P116-RELEASE-PUBLICATION.json';assert not failure.exists();dump(failure,r);raise
 print(json.dumps({'status':r['status'],'url':r['releaseUrl'],'assets':len(r['assets'])}))

if __name__=='__main__':main()
