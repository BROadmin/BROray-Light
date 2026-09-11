"""Observe the existing publisher; a known previous page is pending, not a retry."""
import argparse,datetime,hashlib,json,urllib.request,urllib.parse
from prepare_r0013_release_assets import ROOT
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(p,r):p.write_bytes((json.dumps(r,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--copy-correction',action='store_true');args=parser.parse_args()
 p=ROOT/('checkpoints/R0013/LIVE-DOCUMENTATION-P121.json' if args.copy_correction else 'checkpoints/R0013/LIVE-DOCUMENTATION-P118.json')
 publication=json.loads((ROOT/'checkpoints/R0013/DOC-PUBLICATION-P117.json').read_bytes())
 assert publication['status']=='PASS_GITHUB_DOC_COMMITS_WAIT_EXISTING_WEBSITE_PUBLISHER'
 source=publication['commits'][1]['commit'];revision='p118-existing-publisher-live-byte-observation'
 if args.copy_correction:
  corrected=json.loads((ROOT/'checkpoints/R0013/DOC-CORRECTION-P120.json').read_bytes());assert corrected['status']=='PASS_DOC_CORRECTION_COMMIT_WAIT_EXISTING_PUBLISHER'
  source=corrected['commit'];revision='p121-corrected-light-page-live-byte-observation'
 r=json.loads(p.read_bytes()) if p.exists() else {'schemaVersion':1,'revision':revision,'status':'PENDING_EXISTING_PUBLISHER','sourceCommit':source,'observations':[],'productionServerDirectlyChanged':False}
 assert r['status']=='PENDING_EXISTING_PUBLISHER';dump(p,r)
 try:
  observation={'observedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pages':[]}
  for rel in ('index.html','broray-light/index.html'):
   url='https://docs.brovibe.cloud/'+('' if rel=='index.html' else 'broray-light/')
   req=urllib.request.Request(url,headers={'User-Agent':'BROray-Light-documentation-validation','Cache-Control':'no-cache','Accept-Encoding':'identity'})
   with urllib.request.urlopen(req,timeout=30) as response:
    assert response.status==200 and urllib.parse.urlparse(response.url).hostname=='docs.brovibe.cloud' and response.url.startswith('https://')
    body=response.read(1024*1024+1);assert len(body)<=1024*1024
    content_type=response.headers.get('Content-Type','');assert content_type.startswith('text/html')
   expected=(ROOT/'publication/R0013/site'/rel).read_bytes();old=(ROOT/'publication/R0013/templates'/rel).read_bytes()
   previous_sha=next(x['sha256'] for x in publication['commits'][1]['files'] if x['path']=='site/docs.brovibe.cloud/'+rel)
   assert body in (expected,old) or (args.copy_correction and sha(body)==previous_sha),'Unrecognized live page bytes: '+rel
   observation['pages'].append({'url':url,'path':rel,'status':'PASS' if body==expected else 'PENDING_KNOWN_PREVIOUS_PAGE','httpStatus':200,'contentType':content_type,'bytes':len(body),'sha256':sha(body),'expectedSha256':sha(expected)})
  r['observations'].append(observation)
  if all(x['status']=='PASS' for x in observation['pages']):r.update(status='PASS_LIVE_HOMEPAGE_AND_LIGHT_GUIDE_EXACT_BYTES',websiteLiveVerified=True)
  dump(p,r)
 except Exception as error:
  r.update(status='FAIL_FIRST_ERROR',errorType=type(error).__name__,error=str(error)[:300]);dump(p,r)
  failure=ROOT/('checkpoints/R0013/process-failures/FAILURE-P121-LIVE-DOCUMENTATION.json' if args.copy_correction else 'checkpoints/R0013/process-failures/FAILURE-P118-LIVE-DOCUMENTATION.json');assert not failure.exists();dump(failure,r);raise
 print(json.dumps({'status':r['status'],'observation':observation},ensure_ascii=False))
if __name__=='__main__':main()
