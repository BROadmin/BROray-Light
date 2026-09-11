#!/usr/bin/env python3
"""Validate the active Light configuration with each verified binary, no start/install."""
import hashlib
import io
import json
import sys
import zipfile
from diagnose_r0013_xray_compatibility import REPO, TAGS, Target, digest, now, save


def main():
    out = REPO / 'dist/R0013/p88-current-config-v1'
    out.mkdir(parents=True, exist_ok=False)
    source = REPO / 'dist/R0013/p88-xray-compat-v5'
    accepted = json.loads((source / 'report.json').read_text(encoding='utf-8'))
    assert accepted['status'] == 'PASS_BOUNDED_LOCALHOST' and accepted['installedStatePreserved']
    report = {'schemaVersion': 1, 'revision': 'p88-current-config-v1', 'startedAt': now(),
              'mode': 'xray run -test against existing active config, no listener or install',
              'secretsIncluded': False, 'versions': []}
    target = None
    try:
        target = Target()
        report['before'] = target.snapshot()
        # Config validation must not open a caller-configured durable log file.
        target.command("jq -e '[(.log.access // \"\"),(.log.error // \"\")]|all(.[];.==\"\" or .==\"none\")' /opt/broray-light/config/config.json >/dev/null")
        target.prepare()
        for tag in TAGS:
            reference = next(row for row in accepted['versions'] if row['tag'] == tag)
            archive = (source / (tag + '.zip')).read_bytes()
            assert digest(archive) == reference['archiveSha256']
            with zipfile.ZipFile(io.BytesIO(archive)) as package:
                binary = package.read('xray')
            assert digest(binary) == reference['binarySha256']
            target.put('xray', binary, 0o700)
            result = target.command(f'{target.work}/xray run -test -c /opt/broray-light/config/config.json', check=False)
            combined = (result['stdout'] + result['stderr']).encode()
            row = {'tag': tag, 'binarySha256': digest(binary), 'exitCode': result['exitCode'],
                   'configurationOK': 'Configuration OK.' in result['stdout'],
                   'diagnosticOutputSha256': digest(combined)}
            report['versions'].append(row)
            assert row['exitCode'] == 0 and row['configurationOK'], f'FIRST_ERROR {tag}: active configuration rejected; private contents not printed'
            target.remove(['xray'])
            print(tag + ': active configuration PASS', flush=True)
        report['status'] = 'PASS_7_OF_7_ACTIVE_CONFIGURATION'
    except Exception as exc:
        report['status'] = 'FIRST_ERROR'
        report['error'] = str(exc)
        save(REPO / 'checkpoints/R0013/process-failures/FAILURE-P88-CURRENT-CONFIG-V1.json',
             {'revision': report['revision'], 'at': now(), 'error': str(exc), 'retryPerformed': False,
              'nextRevision': 'p88-current-config-v2-only-after-diagnosis'})
    finally:
        if target:
            try:
                report['cleanup'] = target.cleanup()
                report['after'] = target.snapshot()
                report['installedStatePreserved'] = report['before'] == report['after']
                if not report['installedStatePreserved']:
                    report['status'] = 'INSTALLED_STATE_CHANGED_REQUIRES_DIAGNOSIS'
            except Exception as exc:
                report['cleanup'] = {'status': 'FAIL', 'error': str(exc)}
                report['status'] = 'CLEANUP_BLOCKED'
            target.client.close()
        report['completedAt'] = now()
        print(json.dumps(save(out / 'report.json', report)), flush=True)
    return 0 if report['status'] == 'PASS_7_OF_7_ACTIVE_CONFIGURATION' else 1


if __name__ == '__main__':
    sys.exit(main())
