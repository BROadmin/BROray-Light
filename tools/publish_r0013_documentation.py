"""Bounded GitHub documentation commits; use the existing website publisher."""
import base64,hashlib,json
from prepare_r0013_release_assets import GitHub, ROOT

def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,r):p.write_bytes((json.dumps(r,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 receipt=ROOT/'checkpoints/R0013/DOC-PUBLICATION-P117.json';assert not receipt.exists()
 release=json.loads((ROOT/'checkpoints/R0013/RELEASE-PUBLISH-P116-V2.json').read_bytes())
 assert release['status']=='PASS_PUBLISHED_IMMUTABLE_RELEASE_AND_PUBLIC_BYTES'
 g=GitHub();r={'schemaVersion':1,'revision':'p117-bounded-github-doc-publication','status':'IN_PROGRESS','productionServerDirectlyChanged':False,'fullBROrayApplicationChanged':False,'commits':[]};write(receipt,r)
 def head(repo):return g.request('/repos/BROadmin/'+repo+'/git/ref/heads/main')['object']['sha']
 def content(repo,path,ref):
  d=g.request('/repos/BROadmin/'+repo+'/contents/'+path+'?ref='+ref)
  assert d['type']=='file' and d['encoding']=='base64'
  return base64.b64decode(d['content'])
 def commit(repo,old,files,message):
  base='/repos/BROadmin/'+repo
  tree=g.request(base+'/git/commits/'+old)['tree']['sha'];entries=[]
  for path,body in files.items():
   blob=g.request(base+'/git/blobs',{'content':base64.b64encode(body).decode(),'encoding':'base64'})
   entries.append({'path':path,'mode':'100644','type':'blob','sha':blob['sha']})
  created_tree=g.request(base+'/git/trees',{'base_tree':tree,'tree':entries})
  created=g.request(base+'/git/commits',{'message':message,'tree':created_tree['sha'],'parents':[old]})
  assert head(repo)==old,'Concurrent main change: refuse overwrite'
  g.request(base+'/git/refs/heads/main',{'sha':created['sha'],'force':False},method='PATCH')
  assert head(repo)==created['sha']
  for path,body in files.items():assert content(repo,path,created['sha'])==body
  row={'repository':'BROadmin/'+repo,'before':old,'commit':created['sha'],'files':[{'path':p,'bytes':len(b),'sha256':sha(b)} for p,b in files.items()]}
  r['commits'].append(row);write(receipt,r);return created['sha']
 try:
  light_files={
   'README.md':(ROOT/'publication/R0013/github/README.md').read_bytes(),
   'docs/beginner-installation.md':(ROOT/'docs/beginner-installation.md').read_bytes(),
   'docs/RELEASE-2.0.0.md':(ROOT/'docs/RELEASE-2.0.0.md').read_bytes(),
   'CHANGELOG.md':(ROOT/'CHANGELOG.md').read_bytes()}
  assert all('подготовка к выпуску' not in b.decode().lower() for b in light_files.values())
  commit('BROray-Light',head('BROray-Light'),light_files,'docs: BROray-Light 2.0.0 installation guide and version history')
  old=head('BROray');prefix='site/docs.brovibe.cloud/'
  listing=content('BROray',prefix+'SHA256SUMS',old).decode().splitlines()
  original={};names=[]
  for line in listing:
   expected,name=line.split(None,1);name=name.strip()
   assert len(expected)==64 and name not in names and '..' not in name and not name.startswith('/')
   names.append(name);original[name]=content('BROray',prefix+name,old)
   assert sha(original[name])==expected,'Existing website manifest mismatch '+name
  assert set(names)=={'index.html','styles.css','broray/index.html','broray/beginner-installation/index.html','broray-light/index.html','favicon.ico','favicon-16x16.png','favicon-32x32.png','apple-touch-icon.png','icon-192.png','icon-512.png','site-manifest.json'}
  for name in ('index.html','styles.css','broray-light/index.html'):
   assert original[name]==(ROOT/'publication/R0013/templates'/name).read_bytes(),'Website source changed since preview: '+name
  changed={name:(ROOT/'publication/R0013/site'/name).read_bytes() for name in ('index.html','broray-light/index.html')}
  assert all('подготовка релиза' not in b.decode().lower() and 'приёмка продолжается' not in b.decode().lower() for b in changed.values())
  manifest=''.join(sha(changed.get(n,original[n]))+'  '+n+'\n' for n in names).encode()
  files={prefix+n:b for n,b in changed.items()};files[prefix+'SHA256SUMS']=manifest
  commit('BROray',old,files,'docs: publish BROray-Light 2.0.0 guide, history and homepage card')
  r.update(status='PASS_GITHUB_DOC_COMMITS_WAIT_EXISTING_WEBSITE_PUBLISHER',websiteLiveVerified=False);write(receipt,r)
 except Exception as error:
  r.update(status='FAIL_FIRST_ERROR',errorType=type(error).__name__,error=str(error)[:300]);write(receipt,r)
  failure=ROOT/'checkpoints/R0013/process-failures/FAILURE-P117-DOC-PUBLICATION.json';assert not failure.exists();write(failure,r);raise
 print(json.dumps({'status':r['status'],'commits':[x['commit'] for x in r['commits']]}))
if __name__=='__main__':main()
