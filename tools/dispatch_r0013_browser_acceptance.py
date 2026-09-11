"""Dispatch the existing isolated browser workflow at the verified feature head."""
import json
from prepare_r0013_release_assets import GitHub, ROOT

path=ROOT/'checkpoints/R0013/BROWSER-DISPATCH-P109.json'
assert not path.exists()
g=GitHub()
base='/repos/BROadmin/BROray-Light'
head=g.request(base+'/git/ref/heads/codex/r0009-updater-package')['object']['sha']
assert head=='f4af30d98fd1f227e5116def825c09399437086f'
r={'revision':'p109-exact-source-browser-controls','sourceCommit':head,'status':'DISPATCHING','candidateReady':False}
path.write_bytes((json.dumps(r,indent=2)+'\n').encode())
# GitHub dispatch returns 204, not JSON. Do not interpret JSON decoding as an
# operation failure or resend the dispatch.
import urllib.request
request=urllib.request.Request('https://api.github.com'+base+'/actions/workflows/r0013-browser-controls.yml/dispatches',
    data=json.dumps({'ref':'codex/r0009-updater-package'}).encode(),method='POST',
    headers={'Authorization':'Bearer '+g.token,'Accept':'application/vnd.github+json','Content-Type':'application/json','User-Agent':'BROray-Light-acceptance'})
with g.opener.open(request,timeout=30) as response:
    assert response.status==204
r['status']='DISPATCHED_ONCE'
path.write_bytes((json.dumps(r,indent=2)+'\n').encode())
print(json.dumps(r))
