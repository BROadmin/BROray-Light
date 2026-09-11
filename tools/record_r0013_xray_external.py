#!/usr/bin/env python3
"""Seal existing P89 observations without accessing or mutating the test router."""
import json
import tarfile
from pathlib import Path
from diagnose_r0013_xray_external import CHECKPOINTS as CP, REPO, digest, now, seal, record


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def identity(path):
    data = path.read_bytes()
    return {'path': path.relative_to(REPO).as_posix(), 'sha256': digest(data), 'bytes': len(data)}


def update_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    assert not (CP / 'XRAY-EXTERNAL-P89.json').exists(), 'Immutable final receipt already exists'
    start = read(CP / 'XRAY-EXTERNAL-PREFLIGHT-P89-V2.json')
    v3, v4 = read(CP / 'XRAY-EXTERNAL-P89-V3.json'), read(CP / 'XRAY-EXTERNAL-P89-V4.json')
    assert v3['status'] == 'FIRST_ERROR'
    assert v4['status'] == 'PASS_REMAINING_5_VERSIONS_AND_FINAL_2699_CONTROL'
    for run in (v3, v4):
        assert run['before'] == run['after'] == start['identityAndState']
        assert run['installedStatePreserved'] and run['cleanup']['temporaryDirectoryRemoved']
    assert v3['diagnosticConfigSha256'] == v4['diagnosticConfigSha256']
    assert v3['outboundIdentitySha256'] == v4['outboundIdentitySha256'] == start['outboundIdentitySha256']
    baseline, rejected = v3['versions']
    assert baseline['tag'] == 'v26.9.9' and rejected['tag'] == 'v26.2.6'
    assert rejected['start']['exitCode'] == 0 and rejected['configValidation']['configurationOK']
    assert len(rejected['requests']) == 1 and rejected['requests'][0]['exitCode'] == 35
    positive = [baseline] + v4['versions']
    for row in positive:
        assert row['status'] == 'PASS_3_OF_3_EXTERNAL_HTTPS' and len(row['requests']) == 3
        assert row['configValidation']['configurationOK'] and row['start']['exitCode'] == 0
        assert all(r['status'] == 'PASS_HTTPS_CERTIFICATE_AND_CONTENT' and r['exitCode'] == 0 for r in row['requests'])
    assert len({r['requests'][1]['egressIpSha256'] for r in positive}) == 1
    source = read(CP / 'PRODUCED-SOURCE-MANIFEST.json')
    for row in source['files']:
        assert digest((REPO / row['path']).read_bytes()) == row['sha256'], 'Accepted source changed: ' + row['path']
    donor = REPO / 'dist/R0013/donor-3.1.0-r09/broray-app-3.1.0-r09c02.tar.gz'
    assert digest(donor.read_bytes()) == '635e905d0fb31aff84cd92026dfed21ad204ea45c8d0a5562fecb248178b32e8'
    with tarfile.open(donor) as archive:
        registry = json.loads(archive.extractfile('app/share/xray-compatibility.json').read())
    upstream = next(r for r in registry['records'] if r['xrayTag'] == 'v26.2.6')
    assert upstream['status'] == 'incompatible' and upstream['archiveSha256'] == rejected['archiveSha256']
    donor_id = seal(CP / 'XRAY-UPSTREAM-NEGATIVE-P89.json',
                    {'sourceArchive': identity(donor), 'member': 'app/share/xray-compatibility.json', 'record': upstream})
    rows = []
    for r in [rejected] + v4['versions']:
        failed = r['tag'] == 'v26.2.6'
        rows.append({'version': r['tag'][1:], 'architecture': 'arm64',
            'status': 'INCOMPATIBLE_IN_TESTED_EXTERNAL_SCENARIO' if failed else 'PASS_IN_TESTED_EXTERNAL_SCENARIO',
            'archiveSha256': r['archiveSha256'], 'binarySha256': r['binarySha256'],
            'configurationValidation': 'PASS', 'processStart': 'PASS',
            'httpsPassed': 0 if failed else 3, 'httpsAttempted': len(r['requests']),
            'httpsNotAttemptedAfterFirstError': 2 if failed else 0,
            'firstCurlExitCode': 35 if failed else 0})
    summary = {'schemaVersion': 1, 'revision': 'p89-external-complete', 'at': now(),
        'status': 'COMPLETE_6_PASS_26_2_6_INCOMPATIBLE_IN_TESTED_SCENARIO',
        'target': 'Authorized test Keenetic 192.168.1.1', 'architecture': 'arm64',
        'productVersion': '2.0.0', 'installedSourceCommit': '14813c3774207502039999e014062464043827d1',
        'versions': rows, 'uniqueVersions': 7, 'externalHttpsPasses': 21, 'externalHttpsFailures': 1,
        'countsExplanation': 'Six versions x 3 successes plus an explicitly planned repeated 26.9.9 positive control x 3; 26.2.6 stopped at first failed request.',
        'outboundIdentitySha256': start['outboundIdentitySha256'],
        'diagnosticConfigSha256': v3['diagnosticConfigSha256'],
        'allPositiveControlsSameEgressIpHash': True, 'tlsVerificationDisabled': False,
        'noDirectFallback': True, 'installedVersion': '26.9.9',
        'originalManagedPid': 4340, 'originalManagedStartTicks': '40388289',
        'installedRuntimeAndDurableStatePreserved': True, 'allOwnedRouterScratchRemoved': True,
        'shippedCompatibilityRegistryChanged': False, 'acceptedSourceFilesUnchanged': len(source['files']),
        'priorBROrayNegativeEvidence': donor_id, 'priorBROrayRejectionSuperseded': False,
        'evidence': [identity(CP / 'XRAY-EXTERNAL-PREFLIGHT-P89-V2.json'),
                     identity(CP / 'XRAY-EXTERNAL-P89-V3.json'), identity(CP / 'XRAY-EXTERNAL-P89-V4.json')],
        'testTool': identity(REPO / 'tools/diagnose_r0013_xray_external.py'),
        'findings': [
            '26.2.6 accepts the config and starts, but external HTTPS over the existing VLESS/XHTTP/REALITY server fails with curl 35; the previous rejection is supported, not overturned.',
            '26.3.27, 26.6.27, 26.7.11, 26.7.28, 26.9.8 and 26.9.9 pass three HTTPS endpoints with certificate verification and body checks.',
            '26.9.9 passed before and after the negative test sequence on the same outbound and exit IP.',
            'P88 synthetic localhost results remain valid only within their original scope and do not establish external compatibility.',
            'Raw V3 field tlsVerificationFailed was overbroad for curl 35. Interpret this as a TLS connection failure; no specific certificate rejection or deeper root cause has been established.'
        ],
        'limits': ['Only the current external VLESS/XHTTP/REALITY profile on ARM64; not every server, transport or architecture.',
                   'Separate router-side diagnostic processes, not installing each version as managed runtime. No native restart/update/rollback or browser acceptance claim.',
                   'Same failure class as historic BROray; exact historical server configuration and deeper cause have not been established.',
                   'No UDP, throughput, long-duration load or full release acceptance.'],
        'candidateReady': False, 'releaseReady': False, 'publicReleasePublished': False,
        'nextExactAction': 'RECORD_NEGATIVE_COMPATIBILITY_IN_CANDIDATE_BEFORE_RELEASE_AND_COMPLETE_REMAINING_WEBUI_LIFECYCLE_SIGNING_ACCEPTANCE'}
    final_id = seal(CP / 'XRAY-EXTERNAL-P89.json', summary)
    lines = ['# Xray: реальная внешняя проверка на тестовом роутере', '',
        '11 сентября 2026 года. BROray-Light 2.0.0, ARM64, действующий внешний VLESS/XHTTP/REALITY-сервер.', '',
        '**26.2.6 не прошла проверку. Прежнее отклонение BROray подтверждается, а не отменяется.**', '',
        '| Xray | Проверка конфига / запуск | Внешний HTTPS |', '|---|---|---|']
    for row in rows:
        lines.append(f"| {row['version']} | PASS / PASS | " + ('FAIL: 0/1, curl 35; остальные 2 не запускались' if row['firstCurlExitCode'] else '3/3 PASS') + ' |')
    lines += ['', '26.9.9 отдельно прошла 3/3 до отказа и 3/3 после проверки остальных версий. Итого 21 успешный запрос и 1 отказ; семь уникальных версий. У всех успешных проверок совпадает хеш выходного IP.', '',
        '## Что именно проверено', '',
        'Официальные ARM64-бинарники исполнялись на самом Keenetic. Полный VLESS-outbound взят из действующего конфига без изменения его параметров и проверен по SHA-256. Тестовый вход — SOCKS только на 127.0.0.1:39490; выход только VLESS, без direct fallback. HTTPS: gstatic generate_204, Cloudflare trace, example.com. Проверка сертификатов включена, проверены HTTP-коды и содержимое.', '',
        'У 26.2.6 конфиг и запуск прошли, но первый HTTPS-запрос дал curl 35 (ошибка установления TLS-соединения). Это не доказывает конкретный дефект сертификата или точную внутреннюю причину. По FIRST-ERROR версия не повторялась. Поле tlsVerificationFailed в сырой V3-записи было слишком широким: его следует трактовать с этим уточнением.', '',
        '## Сохранность и ограничения', '',
        'Установленный Xray 26.9.9 не заменялся и не перезапускался. PID 4340 / start ticks 40388289, хеши бинарника, Light и пользовательских данных совпали до и после. Все временные файлы создавались в закрытых каталогах tmpfs и удалены. Реестр совместимости в приложении не менялся.', '',
        'Это проверка передачи данных на текущем внешнем профиле. Она не заменяет установку каждой версии, проверки native lifecycle, браузеров, других серверов/архитектур, UDP и нагрузки. Готовность кандидата и релиза остаётся false.', '',
        '## Сопоставление с BROray', '',
        'В закреплённом архиве BROray 3.1.0-r09c02 версия 26.2.6 отмечена incompatible после R0082/r06: внешний HTTPS 0/3, Firefox и Chrome по 0/3. SHA-256 официального ARM64-архива совпадает с проверенным здесь. Текущий отказ соответствует прежнему классу сбоя. Проверки P88 на localhost не снимают это ограничение.', '',
        '## История первых ошибок', '',
        '- V1: слишком строгая предпроверка потребовала единственный outbound; исправлено выделением единственного VLESS из штатного конфига с direct/block.',
        '- V2: отсутствует nohup; HTTP-запросы не запускались. V3 использует POSIX trap для SIGHUP.',
        '- V3: реальный отказ 26.2.6, остановка и запись ошибки. V4 исключает эту версию и проверяет оставшиеся версии с заключительным положительным контролем.', '',
        'Все записи ошибок и исходные результаты сохранены без перезаписи.', '',
        'Итог: [XRAY-EXTERNAL-P89.json](XRAY-EXTERNAL-P89.json). Отказ: [FAILURE-P89-EXTERNAL-V3.json](process-failures/FAILURE-P89-EXTERNAL-V3.json).', '',
        'SHA-256 итога: `' + final_id['sha256'] + '`.', '']
    report_path = CP / 'XRAY-EXTERNAL-P89.md'
    with report_path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write('\n'.join(lines))
    report_id = identity(report_path)
    record({'revision': summary['revision'], 'status': summary['status'],
            'nextExactAction': summary['nextExactAction']}, final_id)
    state_path = REPO / 'project/R0013-STATE.json'
    state = read(state_path)
    state['xrayExternalDiagnostic']['report'] = report_id
    state['xrayExternalDiagnostic']['incompatibleVersions'] = ['26.2.6']
    state['xrayExternalDiagnostic']['registryUpdatePending'] = True
    update_json(state_path, state)
    handoff_path = REPO / 'docs/CODEX-HANDOFF.md'
    handoff = handoff_path.read_text(encoding='utf-8')
    addition = ('## Current state — R0013 / P89: external Xray compatibility checked\n\n'
        'Actual ARM64 test-router processes using the unchanged active external VLESS/XHTTP/REALITY outbound: 26.2.6 FAIL on first HTTPS request (curl 35), despite config/start PASS. No retry. This supports the prior pinned BROray rejection; P88 localhost PASS must not be interpreted as external compatibility. '
        '26.3.27, 26.6.27, 26.7.11, 26.7.28, 26.9.8 and 26.9.9 each PASS 3/3 HTTPS endpoints with certificate checks. Explicit 26.9.9 before/after controls PASS; all positive exit-IP hashes match. '
        'Installed 26.9.9 PID 4340/start 40388289 and durable hashes preserved; exact private tmpfs cleanup PASS. No installed-version switches, native lifecycle/browser claim, registry edit, release or product source changes. '
        'See checkpoints/R0013/XRAY-EXTERNAL-P89.md and JSON. Before release, incorporate the negative compatibility evidence; complete remaining WebUI/lifecycle/signing acceptance. candidateReady=false, releaseReady=false.\n\n')
    assert handoff.startswith('# Codex handoff\n\n')
    handoff_path.write_text('# Codex handoff\n\n' + addition + handoff[len('# Codex handoff\n\n'):], encoding='utf-8')
    global_report = CP / 'REPORT.md'
    with global_report.open('a', encoding='utf-8') as stream:
        stream.write('\n\n## P89 — внешняя совместимость Xray\n\n'
            '26.2.6: FAIL реального HTTPS через VLESS/XHTTP/REALITY (curl 35), конфиг/запуск PASS. '
            'Остальные шесть версий: по 3/3 PASS; 26.9.9 положительные контроли до/после PASS. '
            'Установленный runtime/PID/данные сохранены, RAM очищена. Это не установка каждой версии и не браузерная приёмка. '
            'Предыдущий отрицательный вывод BROray не отменён. Подробности: [XRAY-EXTERNAL-P89.md](XRAY-EXTERNAL-P89.md).\n')
    validation_path = CP / 'VALIDATION.json'
    validation = read(validation_path)
    validation.update(currentRevision=summary['revision'], nextExactAction=summary['nextExactAction'])
    validation['xrayExternalDiagnostic'] = {**final_id, 'status': summary['status'], 'installedStatePreserved': True,
        'incompatibleVersions': ['26.2.6'], 'shippedRegistryUpdated': False, 'browserOrInstalledVersionLifecycleAcceptance': False}
    validation['acceptanceScope'] += ' P89 now tests the actual external active XHTTP/REALITY server: six versions PASS, 26.2.6 FAIL; this does not close browser or installed-version lifecycle gates.'
    update_json(validation_path, validation)
    checkpoint_path = CP / 'CHECKPOINT.json'
    checkpoint = read(checkpoint_path)
    checkpoint.update(currentRevision=summary['revision'], nextExactAction=summary['nextExactAction'])
    checkpoint['xrayExternalDiagnostic'] = {**final_id, 'report': report_id, 'incompatibleVersions': ['26.2.6']}
    checkpoint['report'] = identity(global_report)
    checkpoint['validation'] = identity(validation_path)
    update_json(checkpoint_path, checkpoint)
    state = read(state_path)
    state['checkpoint'] = identity(checkpoint_path)
    state['report'] = identity(global_report)
    update_json(state_path, state)
    # Only current-state sidecars may change; historical checksum bytes are immutable.
    for path in (CP / 'CHECKPOINT.json', CP / 'REPORT.md', CP / 'VALIDATION.json'):
        sidecar = path.with_name(path.name + '.sha256')
        sidecar.write_text(digest(path.read_bytes()) + '  ' + path.name + '\n', encoding='ascii', newline='\n')
    files = sorted(p for p in CP.rglob('*') if p.is_file() and p.name not in ('SHA256SUMS', 'SHA256SUMS.sha256'))
    sums = CP / 'SHA256SUMS'
    sums.write_text(''.join(digest(p.read_bytes()) + '  ' + p.relative_to(CP).as_posix() + '\n' for p in files), encoding='utf-8', newline='\n')
    sums.with_name('SHA256SUMS.sha256').write_text(digest(sums.read_bytes()) + '  SHA256SUMS\n', encoding='ascii', newline='\n')
    print(json.dumps({'summary': final_id, 'report': report_id, 'checkpoint': identity(checkpoint_path),
                      'sha256Entries': len(files), 'acceptedSourceFilesUnchanged': len(source['files'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
