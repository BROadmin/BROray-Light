"""Stage exact public signed index bytes for pre-publication target checks."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'dist/R0013/p109-release-build/signed'
target=ROOT/'checkpoints/R0013/signed-probe-p112'
assert not target.exists()
assert hashlib.sha256((source/'release.json').read_bytes()).hexdigest()=='64a909aec7f774b74c1819c887435fdd992af9c7f25d048cdc6fce72ac6bb31e'
target.mkdir()
rows=[]
for name in ('release.json','release.json.minisig'):
    body=(source/name).read_bytes();(target/name).write_bytes(body)
    rows.append({'name':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()})
report={'schemaVersion':1,'revision':'p112-signed-index-probe','status':'STAGED_EXACT_PUBLIC_SIGNED_BYTES','sourceCommit':'f4af30d98fd1f227e5116def825c09399437086f','artifacts':rows,'candidateReady':False,'publicReleasePublished':False,'boundary':'Feature branch evidence only, not Stable channel publication; final bundle URL is not downloaded by equal-version check'}
p=ROOT/'checkpoints/R0013/SIGNED-PROBE-P112.json';assert not p.exists();p.write_bytes((json.dumps(report,indent=2)+'\n').encode());print(json.dumps(report))
