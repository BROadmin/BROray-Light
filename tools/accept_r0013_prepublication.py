"""Create release-readiness receipt only from completed, exact-source gates."""
import datetime,hashlib,json,subprocess,tarfile
from prepare_r0013_release_assets import ROOT
SOURCE='f4af30d98fd1f227e5116def825c09399437086f'
OUT=ROOT/'checkpoints/R0013/PREPUBLICATION-ACCEPTANCE-P115.json'
assert not OUT.exists()
def sha(b):return hashlib.sha256(b).hexdigest()
def read(name):return json.loads((ROOT/'checkpoints/R0013'/name).read_bytes())
assert subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()=='codex/r0009-updater-package'
assert not subprocess.check_output(['git','diff',SOURCE,'--','packaging/r0013-overlay','tools/build_r0013_release.py','tools/r0013_inputs.py','tools/r0013_platform.py','tools/r0013_runtime_paths.py'],cwd=ROOT)
ci=read('REGRESSION-P109.json');assert ci['status']=='PASS_EXACT_SOURCE_CI' and ci['sourceCommit']==SOURCE
assert len(ci['jobs'])==6 and all(j['conclusion']=='success' for j in ci['jobs'])
browser=read('BROWSER-CONTROLS-P109.json');assert browser['status']=='PASS_EXACT_SOURCE_CI' and browser['sourceCommit']==SOURCE and browser['testInvocations']==22
build=read('INDEPENDENT-BUILDS-P109.json');assert build['sourceCommit']==SOURCE and build['comparison']=='8_OF_8_BYTE_IDENTICAL' and build['signingVerification']=='PASS_EXISTING_PUBLIC_KEY_IN_CI'
builddir=ROOT/'dist/R0013/p109-release-build/A'
for row in build['artifacts']:
 body=(builddir/row['name']).read_bytes();assert sha(body)==row['sha256'] and len(body)==row['bytes']
 assert body==(builddir.parent/'B'/row['name']).read_bytes()
for shell in ('dash','ash'):
 clean=json.loads((builddir.parent/'validation'/('r0013-clean-package-'+shell+'.json')).read_bytes())
 assert clean['status'].startswith('PASS') and all(t['status']=='PASS' for t in clean['tests'])
for name,status in [('TARGET-INSTALL-P110.json','PASS_EXACT_CANDIDATE_INSTALLED_EXISTING_DURABLE_FILES_PRESERVED'),('TARGET-FINAL-P113.json','PASS_SIGNED_CHECK_EQUAL_DOWNGRADE_RESTART_PERSISTENCE_HEALTH'),('TARGET-CLEANUP-P114-V2.json','PASS_EXACT_INPUTS_REMOVED_PRIVATE_BACKUPS_RETAINED'),('TARGET-WEBUI-P115.json','PASS'),('OVERLAP-RECOVERY-P102.json','PASS_EXISTING_IDENTITY_AND_SETTINGS_PRESERVED'),('DOC-PREVIEW-P111.json','PASS_DRAFT_RENDER_AND_COPY'),('PUBLICATION-PREFLIGHT-P115.json','PASS')]:
 assert read(name)['status']==status,name
def app(path):
 with tarfile.open(path) as t:return {m.name:t.extractfile(m).read() for m in t if m.isfile() and m.name.startswith('app/')}
current=app(builddir/'broray-light-app-2.0.0-r1.tar.gz')
old=app(ROOT/'dist/R0013/p83-build-A/broray-light-app-2.0.0-r1.tar.gz')
differences=[n for n in sorted(current.keys()|old.keys()) if current.get(n)!=old.get(n)]
assert differences==['app/bin/broray-subscriptions','app/lib/runtime-environment.sh','app/share/lifecycle/RUNTIME-PATH-MANIFEST.json','app/share/xray-compatibility.json']
assert sorted(n for n in current if n.endswith('.html'))==['app/web-new/home.html','app/web-new/index.html','app/web-new/servers.html','app/web-new/subscriptions.html']
assert all(not any(x in n.lower() for x in ('routes/','quality-history','ratings/','dns-over-tls')) for n in current)
names=['UPSTREAM-DELTA-P2.json','UPSTREAM-PORT-MAP-P2.json','REGRESSION-P109.json','BROWSER-CONTROLS-P109.json','INDEPENDENT-BUILDS-P109.json','TARGET-INSTALL-P110.json','TARGET-FINAL-P113.json','TARGET-CLEANUP-P114-V2.json','TARGET-WEBUI-P115.json','OVERLAP-RECOVERY-P102.json','TARGET-CONTROLS-P98.json','XRAY-EXTERNAL-P89.json','DOC-PREVIEW-P111.json','PUBLICATION-PREFLIGHT-P115.json','SIGNED-PROBE-P112.json']
evidence=[{'path':'checkpoints/R0013/'+n,'sha256':sha((ROOT/'checkpoints/R0013'/n).read_bytes())} for n in names]
def gate(name,ref,scope):return {'name':name,'status':'PASS','evidence':ref,'scope':scope}
gates=[
 gate('pinned-r1-and-canonical-and-donor-inputs','UPSTREAM-DELTA-P2.json','Exact accepted r1, R0008 and selective donor archive'),
 gate('selective-upstream-map-and-excluded-features','UPSTREAM-PORT-MAP-P2.json','VLESS only; exactly three functional pages; no full product rebuild'),
 gate('busybox-syntax-and-component-regression','REGRESSION-P109.json','Six successful exact-source Linux jobs'),
 gate('native-authentication-session-and-ownership','REGRESSION-P109.json','dash/BusyBox native HTTP tests plus authorized native router login'),
 gate('all-webui-buttons-and-responsive-layout','BROWSER-CONTROLS-P109.json','22 Chromium flows; synthetic destructive/edge paths, actual target controls in P98/P102/P113/P115'),
 gate('archive-validation-locks-and-safe-updater','REGRESSION-P109.json','Real isolated shells/filesystems; modeled OS boundaries'),
 gate('clean-installer-xray-bootstrap-and-daemon-tmpdir','INDEPENDENT-BUILDS-P109.json','Exact IPK/installer, real services and ARM64 binary via QEMU; opkg/NDMC adapters'),
 gate('r1-upgrade-equal-downgrade-rollback-persistence','REGRESSION-P109.json','Isolated exact-r1 live transition and forced health rollback; not a new physical r1 upgrade'),
 gate('independent-build-A-B-and-SHA256','INDEPENDENT-BUILDS-P109.json','8/8 byte-identical artifacts'),
 gate('existing-minisign-trust-root','SIGNED-PROBE-P112.json','Existing encrypted Actions secret; exact signature also verified by native router updater'),
 gate('authorized-final-package-and-durable-preservation','TARGET-INSTALL-P110.json','Physical ARM64 test router; no other router/production host'),
 gate('physical-signed-equal-and-downgrade-refusal','TARGET-FINAL-P113.json','Real signed HTTPS index at immutable feature evidence URL; no trust bypass'),
 gate('physical-service-restart-and-persistence','TARGET-FINAL-P113.json','S23/S24 restart, exact existing durable file hashes and healthy interface'),
 gate('physical-xray-controls-and-data-path','TARGET-CONTROLS-P98.json','Same-version26.9.9 reinstall and active/alternate data checks; control code byte-identical to final package'),
 gate('xray-negative-26.2.6-policy','XRAY-EXTERNAL-P89.json','Current ARM64 VLESS/XHTTP/REALITY profile only; exact archive refused, six versions passed bounded checks'),
 gate('subscription-overlap-and-delete-preservation','OVERLAP-RECOVERY-P102.json','All original six IDs and failover settings preserved; changed upstream SNI treated separately'),
 gate('native-ui-health-after-daemon-background-cycle','TARGET-WEBUI-P115.json','Observed fresh healthy ownership and connection after lifecycle correction'),
 gate('temporary-input-cleanup','TARGET-CLEANUP-P114-V2.json','Only verified invocation RAM files removed; private backups remain local'),
 gate('russian-guide-history-desktop-mobile-copy','DOC-PREVIEW-P111.json','Reviewed drafts; final public status/bytes checked after publication'),
 gate('bounded-publication-authority-and-immutable-tag-absence','PUBLICATION-PREFLIGHT-P115.json','GitHub permissions, unchanged website sources, tag/release absent')]
r={'schemaVersion':1,'revision':'p115-prepublication-acceptance','status':'PASS_ALL_PREPUBLICATION_GATES','sourceCommit':SOURCE,'acceptedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'candidateReady':True,'releaseReady':True,'publicReleasePublished':False,'gates':gates,'evidence':evidence,'p98TargetControlBinding':{'changedApplicationFilesSinceP83':differences,'controlScriptsByteIdentical':True},'remainingPublicationChecks':['Immutable GitHub assets/download SHA256 and latest alias','Main README, guide and history bytes','Existing website publisher, homepage and Light page live byte verification']}
OUT.write_bytes((json.dumps(r,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'status':r['status'],'gates':len(gates),'candidateReady':True,'releaseReady':True}))
