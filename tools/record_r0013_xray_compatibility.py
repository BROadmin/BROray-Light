#!/usr/bin/env python3
"""Generate immutable diagnostic evidence and Russian report from completed runs."""
import hashlib
import json
from pathlib import Path
from diagnose_r0013_xray_compatibility import REPO, TAGS, digest, now, save


def identity(path):
    data = path.read_bytes()
    return {'path': path.relative_to(REPO).as_posix(), 'sha256': digest(data), 'bytes': len(data)}


def main():
    matrix_path = REPO / 'dist/R0013/p88-xray-compat-v5/report.json'
    active_path = REPO / 'dist/R0013/p88-current-config-v1/report.json'
    matrix = json.loads(matrix_path.read_text(encoding='utf-8'))
    active = json.loads(active_path.read_text(encoding='utf-8'))
    resolution_path = REPO / 'checkpoints/R0013/XRAY-ACTIVE-CONFIG-IDENTITY-P88.json'
    resolution = json.loads(resolution_path.read_text(encoding='utf-8'))
    assert matrix['status'] == 'PASS_BOUNDED_LOCALHOST' and matrix['installedStatePreserved']
    assert active['status'] == 'INSTALLED_STATE_CHANGED_REQUIRES_DIAGNOSIS'
    assert resolution['status'] == 'PASS_ORIGINAL_MANAGED_RUNTIME_AND_DURABLE_STATE_PRESERVED'
    snapshots = [matrix['before'], matrix['after'], active['before'], active['after']]
    assert all(s.splitlines()[:6] == snapshots[0].splitlines()[:6] for s in snapshots)
    assert all('18775 39982859' in s.splitlines()[6:] for s in snapshots)
    assert matrix['cleanup']['status'] == active['cleanup']['status'] == 'PASS'
    assert [r['tag'] for r in matrix['versions']] == TAGS
    assert [r['tag'] for r in active['versions']] == TAGS
    cp = REPO / 'checkpoints/R0013'
    evidence = save(cp / 'XRAY-COMPATIBILITY-EVIDENCE-P88.json', {'matrix': matrix, 'activeConfiguration': active, 'identityResolution': resolution})
    rows = []
    for r, a in zip(matrix['versions'], active['versions']):
        assert len(r['tests']) == 13 and all(t['exitCode'] == 0 for t in r['tests'])
        assert a['configurationOK'] and a['exitCode'] == 0 and a['binarySha256'] == r['binarySha256']
        for t in r['tests']:
            assert all('Configuration OK.' in t['logs'][key] for key in ('client-test.log', 'server-test.log'))
        archive = matrix_path.parent / (r['tag'] + '.zip')
        assert digest(archive.read_bytes()) == r['archiveSha256']
        rows.append({'tag': r['tag'], 'prerelease': r['prerelease'], 'archiveSha256': r['archiveSha256'],
                     'binarySha256': r['binarySha256'], 'versionOutput': r['versionOutput'].splitlines()[0],
                     'dataPathCasesPassed': 13, 'generatedConfigurationChecksPassed': 26,
                     'activeConfigurationCheck': 'PASS', 'status': 'PASS_BOUNDED',
                     'receipt': identity(matrix_path.parent / (r['tag'] + '.json'))})
    history = [identity(cp / f'process-failures/FAILURE-P88-XRAY-COMPATIBILITY-V{n}.json') for n in range(1, 5)]
    history.append(identity(cp / 'process-failures/FAILURE-P88-CURRENT-CONFIG-V1-PROCESS-SNAPSHOT.json'))
    summary = {'schemaVersion': 1, 'revision': 'p88-xray-compatibility-complete', 'at': now(),
               'status': 'PASS_BOUNDED_7_VERSIONS', 'product': 'BROray-Light', 'publicVersion': '2.0.0',
               'candidateId': '2.0.0-r1', 'architecture': 'arm64', 'actualKernel': '4.9-ndm-5',
               'installedSourceCommit': '14813c3774207502039999e014062464043827d1',
               'appManifestSha256': '57832490c248a75d0286f142c8553e4b5e7a377336b10f648ee2e2dffb206716',
               'generatorSha256': matrix['generatorSha256'], 'generatorJqSha256': matrix['generatorJqSha256'],
               'versions': rows, 'actualDataPathPasses': 91, 'generatedConfigurationPasses': 182,
               'activeConfigurationPasses': 7, 'installedVersion': '26.9.9',
               'installedStateAndPidPreserved': True, 'routerScratchCleanup': 'PASS_TMPFS_ONLY',
               'latestOfficialStable': '26.3.27', 'officialMetadata': identity(matrix_path.parent / 'official-releases.json'),
               'evidence': evidence, 'rawMatrix': identity(matrix_path), 'rawActiveConfiguration': identity(active_path),
               'activeConfigurationIdentityResolution': identity(resolution_path),
               'testTools': [identity(REPO / 'tools/diagnose_r0013_xray_compatibility.py'),
                             identity(REPO / 'tools/diagnose_r0013_xray_current_config.py')],
               'firstErrorHistory': history,
               'findings': [
                   'Installed 26.9.9 is an official prerelease; official latest stable is 26.3.27.',
                   'All seven binaries run on actual ARM64 kernel and accept exact Light generator output and current active config.',
                   'TCP, WS, gRPC, HTTPUpgrade and XHTTP pass with none and TLS; TCP Vision TLS, TCP Vision REALITY and XHTTP REALITY also pass.',
                   'Xray emits deprecation warnings for WS, gRPC and legacy headers.Host. Current tests pass; future versions need separate review.',
                   'New Xray VLESS server-side private-destination protection requires a one-endpoint allowance in the synthetic loopback fixture only.',
                   'Four failed harness revisions were retained and diagnosed; final V5 full matrix passed without hidden same-revision retry.',
                   'Active config check passed 7/7; overbroad executable PID comparison was resolved by exact managed run/config identity. The role of the exited extra PID is unknown.'
               ],
               'limits': [
                   'Same-version synthetic client/server pairs; not an exhaustive mixed-version server interoperability matrix.',
                   'Real payloads traverse localhost, not production servers, subscriptions, CDN or WAN.',
                   'Current active configuration is parsed/tested, not activated by each alternate version.',
                   'UDP, long-duration load, every optional XHTTP extra/encryption mode, other CPU architectures and other kernels are not covered.',
                   'No package/updater install, downgrade, native authentication change, router reboot or shipped compatibility registry update.'
               ],
               'candidateReady': False, 'releaseReady': False, 'publicReleasePublished': False,
               'nextExactAction': 'REMAINING_WEBUI_BACKEND_EXTERNAL_VLESS_PERSISTENCE_AND_SIGNED_UPDATE_ACCEPTANCE'}
    summary_id = save(cp / 'XRAY-COMPATIBILITY-P88.json', summary)
    lines = ['# Проверка совместимости Xray с BROray-Light 2.0.0', '',
             'Дата: 11 сентября 2026 года. Результат: **PASS в проверенном объёме для всех семи версий.**', '',
             'Проверка выполнена реальными официальными ARM64-бинарниками на тестовом Keenetic (ядро 4.9-ndm-5). '
             'Установленный Xray 26.9.9 не заменялся и не перезапускался. SHA-256 программы, конфигураций, манифеста Light и идентификатор рабочего процесса до/после совпали.', '',
             '| Xray | Канал GitHub | Передача данных | Конфиги генератора | Рабочий конфиг |',
             '|---|---|---:|---:|---|']
    for r in rows:
        lines.append(f"| {r['tag'][1:]} | {'Предварительный' if r['prerelease'] else 'Стабильный'} | 13/13 PASS | 26/26 PASS | PASS |")
    lines += ['', 'Итого: **91 проверка передачи данных, 182 проверки сгенерированных конфигураций и 7 проверок текущего рабочего конфига — PASS.**', '',
              '## Что проверено', '',
              'Код jq взят из установленного, проверенного по SHA-256 генератора Light. Проверены TCP, WebSocket, gRPC, HTTPUpgrade и XHTTP без TLS и с TLS; отдельно TCP+Vision+TLS, TCP+Vision+REALITY и XHTTP+REALITY. '
              'Тестовый клиент не отключает проверку TLS-сертификата: доверие синтетическому сертификату задано только процессу через SSL_CERT_FILE. '
              'curl -k применяется лишь к искусственному HTTPS-получателю данных в стенде. Все слушатели доступны только на 127.0.0.1; временные файлы находились в root-owned 0700 каталоге tmpfs и удалены.', '',
              '## Выводы и ограничения', '',
              '- [26.9.9](https://github.com/XTLS/Xray-core/releases/tag/v26.9.9) — предварительный релиз; [26.3.27](https://github.com/XTLS/Xray-core/releases/tag/v26.3.27) — последний официальный стабильный на дату проверки. Автоматического понижения не выполнялось.',
              '- WS, gRPC и старое поле headers.Host сопровождаются предупреждениями об устаревании. Это риск следующих версий, а не отказ текущих проверок.',
              '- Пары клиент/сервер использовали одинаковую версию Xray. Не проверялись все смешанные версии серверов, реальные подписки/CDN/WAN, UDP, длительная нагрузка, все дополнительные параметры XHTTP и другие архитектуры.',
              '- Текущий конфиг проверен командой run -test: переключение реального соединения на каждую версию не выполнялось.',
              '- Реестр совместимости в WebUI не изменён. Готовность всего кандидата/релиза остаётся false: эта проверка не заменяет оставшиеся приёмки.', '',
              '## Контрольные суммы официальных ARM64-архивов', '',
              '| Xray | SHA-256 Xray-linux-arm64-v8a.zip |', '|---|---|']
    for r in rows: lines.append(f"| {r['tag'][1:]} | {r['archiveSha256']} |")
    lines += ['', '## История первых ошибок', '',
              'V1: BusyBox не поддерживает дробный sleep; исправлены интервалы ожидания. '
              'V2: синтетический VLESS-сервер блокировал частный адрес; разрешён ровно тестовый localhost:39488. '
              'V3/V4: TLS-узел REALITY не соответствовал требованиям параллельных проверок; V5 использует отдельный конкурентный TLS-узел. '
              'Ни одна из этих ревизий не повторялась скрыто. Все JSON ошибок сохранены, очистка и сохранность рабочей установки подтверждены.', '',
              'Отдельно сохранено ложное срабатывание широкого сравнения PID: завершился дополнительный процесс с тем же исполняемым файлом. Его прежняя роль неизвестна. Проверка точного run/config-процесса подтвердила сохранение основного PID 18775 и времени его старта; конфиги и бинарники также не менялись. Семь проверок конфига не повторялись.', '',
              'Машиночитаемый итог: [XRAY-COMPATIBILITY-P88.json](XRAY-COMPATIBILITY-P88.json). '
              'Полные журналы: [XRAY-COMPATIBILITY-EVIDENCE-P88.json](XRAY-COMPATIBILITY-EVIDENCE-P88.json).', '',
              f"SHA-256 итога: {summary_id['sha256']}", f"SHA-256 полных журналов: {evidence['sha256']}", '']
    report_path = cp / 'XRAY-COMPATIBILITY-P88.md'
    with report_path.open('x', encoding='utf-8', newline='\n') as report_file:
        report_file.write('\n'.join(lines))
    print(json.dumps({'summary': summary_id, 'evidence': evidence, 'report': identity(report_path)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
