"""Reconcile current release records, preserving prior summaries byte-for-byte."""
import datetime,hashlib,json,subprocess
from pathlib import Path
from prepare_r0013_release_assets import ROOT

CP=ROOT/'checkpoints/R0013'
REV='p122-published-release-and-documentation-final-seal'
NEXT='OPERATE_STABLE_2_0_0_COLLECT_USER_FEEDBACK_AUTHORIZE_NEXT_CHANGE'
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,b):p.write_bytes(b)
def dump(p,r):write(p,(json.dumps(r,ensure_ascii=False,indent=2)+'\n').encode())
def read(n):return json.loads((CP/n).read_bytes())
def ref(p):
 p=Path(p);b=p.read_bytes();return {'path':p.relative_to(ROOT).as_posix(),'sha256':sha(b),'bytes':len(b)}
def seal(p,replace=False):
 b=p.read_bytes();side=p.with_name(p.name+'.sha256');line=(sha(b)+'  '+p.name+'\n').encode()
 if side.exists() and not replace:assert side.read_bytes()==line,'Historical sidecar mismatch '+str(p)
 write(side,line)
def main():
 out=CP/'FINAL-SEAL-P122.json';assert not out.exists(),'No implicit retry'
 r={'schemaVersion':1,'revision':REV,'status':'CHECKPOINT_FIRST','nextExactAction':'VERIFY_ALL_RECEIPTS_THEN_RECONCILE_CURRENT_SUMMARIES'};dump(out,r)
 try:
  source='f4af30d98fd1f227e5116def825c09399437086f'
  assert subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()=='codex/r0009-updater-package'
  assert not subprocess.check_output(['git','diff',source,'--','packaging/r0013-overlay','tools/build_r0013_release.py','tools/r0013_inputs.py','tools/r0013_platform.py','tools/r0013_runtime_paths.py','src'],cwd=ROOT)
  acceptance=read('PREPUBLICATION-ACCEPTANCE-P115.json');assert acceptance['candidateReady'] and acceptance['releaseReady'] and all(g['status']=='PASS' for g in acceptance['gates'])
  for item in acceptance['evidence']:assert sha((ROOT/item['path']).read_bytes())==item['sha256']
  release=read('RELEASE-PUBLISH-P116-V2.json');assert release['status']=='PASS_PUBLISHED_IMMUTABLE_RELEASE_AND_PUBLIC_BYTES'
  assert len(release['assets'])==11 and release['previousAssetsPreserved'] and release['latestVerified']
  for item in release['assets']:assert item['publicBytesVerified'] and sha((ROOT/'dist/R0013/public-v2.0.0'/item['name']).read_bytes())==item['sha256']
  docs=read('DOC-PUBLICATION-P117.json');assert docs['status']=='PASS_GITHUB_DOC_COMMITS_WAIT_EXISTING_WEBSITE_PUBLISHER'
  corrected=read('DOC-CORRECTION-P120.json');assert corrected['status']=='PASS_DOC_CORRECTION_COMMIT_WAIT_EXISTING_PUBLISHER'
  live=read('LIVE-DOCUMENTATION-P121.json');assert live['status']=='PASS_LIVE_HOMEPAGE_AND_LIGHT_GUIDE_EXACT_BYTES'
  web=read('PUBLIC-DOC-BROWSER-P121.json');assert web['status']=='PASS' and len(web['copyTests'])==10 and all(t['status']=='PASS' for t in web['copyTests'])
  native=read('TARGET-STABLE-P119.json');assert native['status']=='PASS' and native['relation']=='equal' and not native['updateAvailable']
  for row in docs['commits'][0]['files']:assert sha((ROOT/row['path']).read_bytes())==row['sha256']
  for row in live['observations'][-1]['pages']:assert sha((ROOT/'publication/R0013/site'/row['path']).read_bytes())==row['sha256']
  baseline=read('PREEXISTING-WORKTREE-P1.json');excluded={'AGENTS.md','project/R0012-STATE.json','project/WORKLOG.jsonl'}
  checked=[x for x in baseline['files'] if x['path'] not in excluded]
  for row in checked:assert sha((ROOT/row['path']).read_bytes())==row['sha256'],'Inherited work changed '+row['path']
  preservation={'schemaVersion':1,'revision':REV,'status':'PASS','checkedFiles':len(checked),'excluded':sorted(excluded),'exceptionEvidence':'R0012-PRESERVATION-P16.json','mismatches':[]}
  dump(CP/'R0012-PRESERVATION-P122.json',preservation);seal(CP/'R0012-PRESERVATION-P122.json')
  # Current summary files are mutable; retain their complete previous bytes first.
  history=CP/'history/P122-BEFORE-SEAL';assert not history.exists();history.mkdir(parents=True)
  snapshots=[]
  oldnames=['checkpoints/R0013/CHECKPOINT.json','checkpoints/R0013/VALIDATION.json','checkpoints/R0013/REPORT.md','checkpoints/R0013/SHA256SUMS','project/R0013-STATE.json','project/IMPLEMENTATION-STATE.json','docs/CODEX-HANDOFF.md']
  for name in oldnames:
   dest=history/name.replace('/','__');write(dest,(ROOT/name).read_bytes());seal(dest);snapshots.append({'originalPath':name,**ref(dest)})
  gates=list(acceptance['gates'])
  extra=[('public-release-assets-and-latest-alias','RELEASE-PUBLISH-P116-V2.json','11 exact public files; signature and index aliases; previous assets preserved'),('github-russian-guide-and-version-history','DOC-PUBLICATION-P117.json','Four exact Light main documentation files; no local branch switch'),('live-homepage-and-light-guide','LIVE-DOCUMENTATION-P121.json','Existing automatic site publisher; exact HTTPS bodies'),('live-doc-copy-controls-and-responsive-layout','PUBLIC-DOC-BROWSER-P121.json','Five real clipboard clicks each at390/1440px; local code scrolling only'),('native-public-stable-check','TARGET-STABLE-P119.json','Actual authenticated updater check: equal2.0.0-r1, healthy installed2.0.0'),('inherited-r0012-preserved','R0012-PRESERVATION-P122.json','502 original code/history files, with previously documented routing/log exceptions')]
  gates += [{'name':n,'status':'PASS','evidence':e,'scope':s} for n,e,s in extra]
  evidence={x['path']:x for x in acceptance['evidence']}
  for n in ['PREPUBLICATION-ACCEPTANCE-P115.json','RELEASE-PUBLISH-P116-V2.json','DOC-PUBLICATION-P117.json','DOC-CORRECTION-P120.json','LIVE-DOCUMENTATION-P121.json','PUBLIC-DOC-BROWSER-P121.json','TARGET-STABLE-P119.json','R0012-PRESERVATION-P122.json']:
   item=ref(CP/n);evidence[item['path']]=item
  validation={'schemaVersion':2,'stage':'R0013','revision':REV,'status':'PASS_ALL_ACCEPTANCE_AND_PUBLICATION_GATES','publicVersion':'2.0.0','releaseId':'2.0.0-r1','sourceCommit':source,'candidateReady':True,'releaseReady':True,'publicReleasePublished':True,'gates':gates,'passed':len(gates),'failed':0,'evidence':list(evidence.values()),'remainingGates':[],'nextExactAction':NEXT}
  dump(CP/'VALIDATION.json',validation);seal(CP/'VALIDATION.json',True)
  artifacts=[{k:x[k] for k in ('name','bytes','sha256','url')} for x in release['assets']]
  artifact_lines='\n'.join('| '+x['name']+' | '+str(x['bytes'])+' | `'+x['sha256']+'` |' for x in artifacts)
  gate_lines='\n'.join('| '+g['name']+' | PASS | ['+g['evidence']+']('+g['evidence']+') |' for g in gates)
  report=f'''# BROray-Light 2.0.0 — итог выпуска R0013

**PASS. Stable 2.0.0 опубликован 11 сентября 2026 года.** candidateReady=true, releaseReady=true, publicReleasePublished=true. Все {len(gates)} итоговых gate — PASS; 20 выполнены до публикации, остальные подтверждают публичные файлы, документацию и сохранность прежней работы.

[Релиз]({release['releaseUrl']}) · [GitHub](https://github.com/BROadmin/BROray-Light) · [Пошаговая инструкция](https://docs.brovibe.cloud/broray-light/) · [История версий](https://github.com/BROadmin/BROray-Light/blob/main/CHANGELOG.md).

## Идентичность и проверки

- Исходный commit точных сборок: `{source}`. Неизменяемый release tag v2.0.0: `{release['releaseCommit']}`.
- Независимые Build A/B P109: **8/8 файлов побайтно идентичны**. Подпись существующим ключом в Actions; приватный ключ не извлекался.
- CI34594794089: **6 заданий PASS**, 41 JSON-отчёт, 511 выполнений проверок (включая повторные preflight, не 511 уникальных сценариев). Chromium34594934644: **22 сценария PASS**.
- Изолированно: clean install с точным Xray, переход с принятого r1, equal-version, downgrade refusal, forced-health rollback, persistence, native auth/session/ownership и RAM-жизненный цикл. Границы OS-адаптеров указаны в acceptance receipts.
- Авторизованный ARM64-роутер: точный финальный пакет, native-вход, реальные проверки/переключение серверов с восстановлением исходного, переустановка Xray26.9.9, signed equal/downgrade, перезапуск S23/S24, сохранность файлов, работа интерфейса после фонового цикла. Новый физический переход с r1 и перезагрузка всего роутера в финальном цикле не заявляются.
- Конечное наблюдение: Light2.0.0, Xray26.9.9, Proxy0 активен, соединение работает, публичный Stable-check возвращает equal2.0.0-r1 без обновления. Шесть исходных серверов и пользовательская подписка сохранены; тестовая подписка удалена отдельно с проверкой.
- Xray26.2.6: config/start PASS, первый внешний HTTPS FAIL(curl35); оставшиеся два запроса NOT_RUN. Точный архив запрещён. Остальные шесть версий PASS только для проверенного ARM64 VLESS/XHTTP/REALITY-профиля. Xray26.9.9 остаётся upstream prerelease.
- Операционные временные файлы находятся в защищённой RAM; собственный TMPDIR сервиса не зависит от удалённого каталога установщика. Постоянно около35МиБ вместе с Xray, app-slot858363байта;80МиБ — рекомендуемый запас, не размер Light.

## Публичная документация

Light main docs commit: `{docs['commits'][0]['commit']}`. Главная сайта и отдельная страница Light опубликованы существующим механизмом; последняя исправленная страница в commit `{corrected['commit']}` полного репозитория затрагивает только документацию и её SHA256SUMS. Прямых изменений production-сервера и приложения полного BROray нет. Руководство не добавлено в WebUI.

Обе живые страницы совпали по SHA-256; инструкция содержит 10 последовательных разделов, проверяемую команду установки, обновление, работу с подписками/Xray, диагностику, удаление и историю версий. Все пять кнопок копирования проверены реальными кликами на390px и1440px; исправлено перекрытие кнопки длинным кодом.

## Опубликованные артефакты

| Файл | Байт | SHA-256 |
| --- | ---: | --- |
{artifact_lines}

## Результаты всех acceptance gates

| Gate | Итог | Evidence |
| --- | --- | --- |
{gate_lines}

## Сохранённые ошибки и границы

Каждая material failure сохранена отдельно в process-failures с SHA-256. P104/P108: унаследованный TMPDIR исправлен в P109 и проверен новыми A/B, полным CI и физическим пакетом. P116: проверяющий скрипт использовал draft URLs; P116-V2 сверил окончательные URL без повторной загрузки файлов или изменения тега. P119: мобильная кнопка копирования на сайте перекрывалась кодом; P120/P121 исправляют только документацию. Прежние ошибочные receipts не переписаны. {len(checked)} исходных файлов R0012 сохранены. Старые сводки до этого seal сохранены побайтно в history/P122-BEFORE-SEAL.

## Следующий этап

`{NEXT}`. Эксплуатация выпущенного Stable и сбор обратной связи; любые новые изменения — отдельная согласованная версия. Не переписывать v2.0.0 или прежние релизы.
'''
  write(CP/'REPORT.md',report.encode());seal(CP/'REPORT.md',True)
  checkpoint={'schemaVersion':2,'stage':'R0013_SELECTIVE_UPSTREAM_STABLE_PORT','status':'PASS_RELEASE_PUBLISHED_AND_DOCUMENTATION_VERIFIED','currentRevision':REV,'publicVersion':'2.0.0','packageVersion':'2.0.0','releaseId':'2.0.0-r1','candidateId':'2.0.0-r1','releaseTag':'v2.0.0','branch':'codex/r0009-updater-package','buildSourceCommit':source,'releaseCommit':release['releaseCommit'],'candidateReady':True,'releaseReady':True,'publicReleasePublished':True,'releaseUrl':release['releaseUrl'],'buildA':'PASS_P109','buildB':'PASS_P109','buildComparison':'8_OF_8_BYTE_IDENTICAL','buildEvidence':ref(CP/'INDEPENDENT-BUILDS-P109.json'),'regression':ref(CP/'REGRESSION-P109.json'),'browser':ref(CP/'BROWSER-CONTROLS-P109.json'),'acceptanceGatesPassed':len(gates),'validation':ref(CP/'VALIDATION.json'),'report':ref(CP/'REPORT.md'),'artifacts':artifacts,'githubDocumentationCommit':docs['commits'][0]['commit'],'websiteSourceCommit':corrected['commit'],'websiteLiveVerified':True,'targetStableCheck':ref(CP/'TARGET-STABLE-P119.json'),'fullBROrayApplicationChanged':False,'fullBROrayRepositoryDocumentationOnlyChanged':True,'productionServerDirectlyChanged':False,'preexistingR0012CodeAndHistoryPreserved':True,'activeFailure':None,'remainingGates':[],'historicalSummarySnapshots':snapshots,'nextExactAction':NEXT}
  dump(CP/'CHECKPOINT.json',checkpoint);seal(CP/'CHECKPOINT.json',True)
  state={**checkpoint,'schemaVersion':2,'workingBranch':checkpoint['branch'],'completedGates':[g['name'] for g in gates],'checkpoint':ref(CP/'CHECKPOINT.json'),'baseLightCommit':'9e5fce9bfa7c82bfc2f2654d80fd3987c5259963','canonicalSourceCommit':'684b27bdb53e545047419baa87c63dd86dffa469','historyIsNotCurrentState':True}
  dump(ROOT/'project/R0013-STATE.json',state)
  previous=json.loads((history/'project__IMPLEMENTATION-STATE.json').read_bytes())
  impl={'schemaVersion':2,'product':'BROray-Light','stage':'R0013','status':checkpoint['status'],'publicVersion':'2.0.0','candidateId':'2.0.0-r1','releaseId':'2.0.0-r1','candidateReady':True,'releaseReady':True,'publicReleasePublished':True,'canonicalSourceCommit':state['canonicalSourceCommit'],'candidateCheckpoint':state['checkpoint']['path'],'candidateCheckpointSha256':state['checkpoint']['sha256'],'validationReceipt':'checkpoints/R0013/VALIDATION.json','validationSha256':checkpoint['validation']['sha256'],'report':'checkpoints/R0013/REPORT.md','reportSha256':checkpoint['report']['sha256'],'r0013':checkpoint,'r0010':previous['r0010'],'r0011':previous['r0011'],'historicalImplementationSnapshot':ref(history/'project__IMPLEMENTATION-STATE.json'),'codexEntryPoint':'docs/CODEX-HANDOFF.md','nextStage':NEXT}
  dump(ROOT/'project/IMPLEMENTATION-STATE.json',impl)
  handoff=f'''# Codex handoff

## Current accepted state — R0013 / 2.0.0 published

R0013 is PASS. candidateReady=true, releaseReady=true, publicReleasePublished=true. Immutable tag v2.0.0 resolves to `{release['releaseCommit']}`; exact build/source commit is `{source}`. Release: {release['releaseUrl']}.

Read docs/CODEX-R0013.md, project/R0013-STATE.json, checkpoints/R0013/CHECKPOINT.json and VALIDATION.json. All26 final gates PASS, including20 prepublication gates, independent A/B8of8, six-job511-invocation CI,22 Chromium flows, authorized target tests,11 public assets, both latest aliases, GitHub Russian guide/history and live site.

Test router has Light2.0.0/internal2.0.0-r1, Xray26.9.9(upstream prerelease), active healthy Proxy0 and connected original user server. Six original server IDs and original subscription were preserved; disposable test subscription was removed. Do not clear/reset user data. P113 service restart and durable preservation PASS; P119 real public Stable check equal/no-update PASS. Exact26.2.6 archive remains forbidden after external HTTPS failure; do not use P88 localhost tests to override P89 external evidence.

Final docs: Light main `{docs['commits'][0]['commit']}`; existing website source `{corrected['commit']}`. Homepage and /broray-light/ live SHA verified. The guide stays on GitHub/site, not in WebUI. Full BROray application and production-server configuration unchanged; only bounded docs source was published through the existing mechanism.

P116 draft-URL validation failure was resolved read-only in P116-V2; no release assets/tag were overwritten. P119 mobile doc-copy layout failure was corrected in site-only P120/P121. Earlier false interface health was a daemon TMPDIR lifetime bug, fixed in final P109 app bytes and fully retested. All failed revisions remain preserved. Historical current-state summaries are archived at checkpoints/R0013/history/P122-BEFORE-SEAL; they are not current instructions or current status.

Keep local branch codex/r0009-updater-package. Preserve all inherited dirty/untracked R0012 work; do not include it in a release. Private off-router backups remain ignored under dist/R0013/private-target and must never be committed. Completed invocation-owned RAM scratch was removed; no router reinstall, restart or service job is in flight.

## Exact next stage

`{NEXT}`. User feedback/normal operation. Do not republish immutable v2.0.0, move tags, migrate documentation hosting or change product code without a new scoped request.
'''
  write(ROOT/'docs/CODEX-HANDOFF.md',handoff.encode())
  r.update(status='PASS_SEALED_CURRENT_RELEASE_RECORDS',candidateReady=True,releaseReady=True,publicReleasePublished=True,checkpoint=ref(CP/'CHECKPOINT.json'),validation=ref(CP/'VALIDATION.json'),report=ref(CP/'REPORT.md'),projectState=ref(ROOT/'project/R0013-STATE.json'),implementationState=ref(ROOT/'project/IMPLEMENTATION-STATE.json'),handoff=ref(ROOT/'docs/CODEX-HANDOFF.md'),gatesPassed=len(gates),nextExactAction=NEXT);dump(out,r);seal(out)
  for p in CP.rglob('*.sha256'):
   target=p.with_name(p.name[:-7])
   if target.exists() and target.name!='SHA256SUMS':assert p.read_text().split()[0]==sha(target.read_bytes()),str(p)
  rows=[p for p in CP.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and not p.name.endswith('.sha256')]
  write(CP/'SHA256SUMS',''.join(sha(p.read_bytes())+'  '+p.relative_to(CP).as_posix()+'\n' for p in sorted(rows)).encode());seal(CP/'SHA256SUMS',True)
  entry={'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stage':'R0013','revision':REV,'status':r['status'],'records':[ref(out),ref(CP/'SHA256SUMS')],'nextExactAction':NEXT}
  with (ROOT/'project/WORKLOG.jsonl').open('ab') as f:f.write((json.dumps(entry,ensure_ascii=False)+'\n').encode())
 except Exception as error:
  r.update(status='FAIL_FIRST_ERROR',errorType=type(error).__name__,error=str(error)[:300]);dump(out,r)
  failure=CP/'process-failures/FAILURE-P122-FINAL-SEAL.json';assert not failure.exists();dump(failure,r);seal(failure);raise
 print(json.dumps({'status':r['status'],'gates':r['gatesPassed'],'checkpoint':r['checkpoint']}))
if __name__=='__main__':main()
