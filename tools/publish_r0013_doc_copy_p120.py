"""Publish a verified Light-page-only correction through the existing publisher."""
import base64,hashlib,json
from prepare_r0013_release_assets import GitHub,ROOT
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(p,r):p.write_bytes((json.dumps(r,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 out=ROOT/'checkpoints/R0013/DOC-CORRECTION-P120.json';assert not out.exists()
 previous=json.loads((ROOT/'checkpoints/R0013/DOC-PUBLICATION-P117.json').read_bytes())['commits'][1]
 preview=json.loads((ROOT/'checkpoints/R0013/DOC-COPY-PREVIEW-P120.json').read_bytes());assert preview['status']=='PASS'
 body=(ROOT/'publication/R0013/site/broray-light/index.html').read_bytes();assert sha(body)==preview['pageSha256']
 r={'schemaVersion':1,'revision':'p120-light-guide-copy-layout-publication','status':'IN_PROGRESS','productionServerDirectlyChanged':False,'fullBROrayApplicationChanged':False,'previousCommit':previous['commit']};dump(out,r)
 try:
  g=GitHub();base='/repos/BROadmin/BROray';prefix='site/docs.brovibe.cloud/'
  old=g.request(base+'/git/ref/heads/main')['object']['sha'];assert old==previous['commit'],'Concurrent site revision refused'
  def content(path,ref):
   d=g.request(base+'/contents/'+path+'?ref='+ref);assert d['encoding']=='base64';return base64.b64decode(d['content'])
  manifest=content(prefix+'SHA256SUMS',old).decode().splitlines();lines=[]
  for line in manifest:
   expected,name=line.split(None,1);name=name.strip();original=content(prefix+name,old);assert sha(original)==expected
   if name=='broray-light/index.html':
    assert expected==next(x['sha256'] for x in previous['files'] if x['path']==prefix+name)
    expected=sha(body)
   lines.append(expected+'  '+name+'\n')
  files={prefix+'broray-light/index.html':body,prefix+'SHA256SUMS':''.join(lines).encode()}
  tree=g.request(base+'/git/commits/'+old)['tree']['sha'];entries=[]
  for path,b in files.items():
   blob=g.request(base+'/git/blobs',{'content':base64.b64encode(b).decode(),'encoding':'base64'})
   entries.append({'path':path,'mode':'100644','type':'blob','sha':blob['sha']})
  newtree=g.request(base+'/git/trees',{'base_tree':tree,'tree':entries})
  commit=g.request(base+'/git/commits',{'message':'docs: keep Light copy controls outside scrollable code blocks','tree':newtree['sha'],'parents':[old]})
  assert g.request(base+'/git/ref/heads/main')['object']['sha']==old
  g.request(base+'/git/refs/heads/main',{'sha':commit['sha'],'force':False},method='PATCH')
  assert g.request(base+'/git/ref/heads/main')['object']['sha']==commit['sha']
  for path,b in files.items():assert content(path,commit['sha'])==b
  r.update(status='PASS_DOC_CORRECTION_COMMIT_WAIT_EXISTING_PUBLISHER',commit=commit['sha'],files=[{'path':p,'sha256':sha(b),'bytes':len(b)} for p,b in files.items()]);dump(out,r)
 except Exception as error:
  r.update(status='FAIL_FIRST_ERROR',errorType=type(error).__name__,error=str(error)[:300]);dump(out,r)
  failure=ROOT/'checkpoints/R0013/process-failures/FAILURE-P120-DOC-CORRECTION.json';assert not failure.exists();dump(failure,r);raise
 print(json.dumps({'status':r['status'],'commit':r['commit']}))
if __name__=='__main__':main()
