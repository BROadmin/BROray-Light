"""Read-only recovery: resolve final URLs, never recreate or modify a release."""
import hashlib,json,urllib.request,urllib.parse
from prepare_r0013_release_assets import GitHub, ROOT

def sha(b):return hashlib.sha256(b).hexdigest()
def dump(p,r):p.write_bytes((json.dumps(r,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 out=ROOT/'checkpoints/R0013/RELEASE-PUBLISH-P116-V2.json';assert not out.exists()
 old=json.loads((ROOT/'checkpoints/R0013/RELEASE-PUBLISH-P116.json').read_bytes())
 assert old['publicReleasePublished'] and old['status']=='FAIL_FIRST_ERROR'
 r={'schemaVersion':1,'revision':'p116-v2-canonical-public-urls-read-only','status':'IN_PROGRESS','previousFailure':'process-failures/FAILURE-P116-RELEASE-PUBLICATION.json','externalMutationPerformed':False,'assets':[]};dump(out,r)
 try:
  g=GitHub();base='/repos/BROadmin/BROray-Light';release=g.request(base+'/releases/'+str(old['releaseId']))
  assert release['tag_name']=='v2.0.0' and not release['draft'] and not release['prerelease']
  assert g.request(base+'/git/ref/tags/v2.0.0')['object']['sha']==old['releaseCommit']
  assert g.request(base+'/releases/latest')['id']==release['id']
  r.update(releaseId=release['id'],releaseUrl=release['html_url'],publishedAt=release['published_at'],publicReleasePublished=True,releaseCommit=old['releaseCommit'],sourceCommit=old['sourceCommit'])
  assets={x['name']:x for x in release['assets']};assert set(assets)=={x['name'] for x in old['assets']}
  def download(url):
   req=urllib.request.Request(url,headers={'User-Agent':'BROray-Light-public-release-P116-V2','Cache-Control':'no-cache','Accept-Encoding':'identity'})
   with urllib.request.urlopen(req,timeout=45) as response:
    assert response.status==200 and response.url.startswith('https://')
    body=response.read(30*1024*1024+1);assert len(body)<=30*1024*1024
    return body,{'status':response.status,'finalUrlHost':urllib.parse.urlparse(response.url).hostname,'contentType':response.headers.get('Content-Type')}
  for original in old['assets']:
   item=assets[original['name']]
   assert item['id']==original['id'] and item['size']==original['bytes'] and item['digest']=='sha256:'+original['sha256']
   url=item['browser_download_url'];assert '/releases/download/v2.0.0/' in url
   body,headers=download(url);assert len(body)==original['bytes'] and sha(body)==original['sha256']
   assert body==(ROOT/'dist/R0013/public-v2.0.0'/original['name']).read_bytes()
   r['assets'].append({**original,'url':url,'publicBytesVerified':True,'publicResponse':headers});dump(out,r)
   print('Public bytes verified: '+original['name'],flush=True)
  r['latestAliases']=[]
  for name in ('release.json','release.json.minisig'):
   url='https://github.com/BROadmin/BROray-Light/releases/latest/download/'+name
   body,headers=download(url);assert body==(ROOT/'dist/R0013/public-v2.0.0'/name).read_bytes()
   r['latestAliases'].append({'url':url,'sha256':sha(body),'bytes':len(body),'response':headers})
  previous=g.request(base+'/releases/'+str(old['previousLatest']['id']))
  assert [{'id':x['id'],'name':x['name'],'size':x['size'],'digest':x.get('digest')} for x in previous['assets']]==old['previousAssets']
  r.update(status='PASS_PUBLISHED_IMMUTABLE_RELEASE_AND_PUBLIC_BYTES',latestVerified=True,previousAssetsPreserved=True);dump(out,r)
 except Exception as error:
  r.update(status='FAIL_FIRST_ERROR',errorType=type(error).__name__,error=str(error)[:300]);dump(out,r)
  failure=ROOT/'checkpoints/R0013/process-failures/FAILURE-P116-V2-PUBLIC-BYTES.json';assert not failure.exists();dump(failure,r);raise
 print(json.dumps({'status':r['status'],'url':r['releaseUrl'],'assets':len(r['assets'])}))
if __name__=='__main__':main()
