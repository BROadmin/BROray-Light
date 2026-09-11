#!/usr/bin/env python3
"""Pinned-donor Xray catalog and explicit-consent policy tests; no downloads/install."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from test_r0013_process import shell_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--shell', default=shutil.which('dash') or shutil.which('sh'))
    parser.add_argument('--jq', default=shutil.which('jq'))
    args = parser.parse_args()
    assert args.shell and args.jq
    assert os.name == 'posix', 'Use Linux: Windows jq cannot load modules from this Cyrillic workspace path.'
    root = Path(__file__).resolve().parents[1] / 'packaging/r0013-overlay/app'
    lib = root / 'lib'
    results = []

    def check(name: str, condition: bool, detail=None) -> None:
        assert condition, (name, detail)
        results.append({'test': name, 'status': 'PASS'})

    def jq(value, expression: str):
        return subprocess.run([args.jq, '-c', '-e', '-L', str(lib), 'include "xray-releases"; ' + expression],
                              input=json.dumps(value), text=True, capture_output=True, encoding='utf-8')

    for tag in ['v26.9.9', 'v26.7.28', 'v26.9.9-beta.1']:
        valid = jq(tag, 'valid_tag')
        check('valid-tag:' + tag, valid.returncode == 0, valid.stderr)
    for tag in ['../../x', 'v26.9.9/evil', 'v26.9.9?url=x', 'v26.9.9\n', 'v26.9.9;id', '', None, []]:
        check('reject-tag:' + repr(tag), jq(tag, 'valid_tag').returncode != 0)

    digest = 'a' * 64

    def release(tag='v26.9.9', prerelease=False):
        prefix = 'https://github.com/XTLS/Xray-core/releases/download/' + tag + '/'
        return {'tag_name': tag, 'draft': False, 'prerelease': prerelease, 'published_at': '2026-09-09T00:00:00Z',
                'assets': [{'id': 1, 'name': 'Xray-linux-arm64-v8a.zip', 'state': 'uploaded', 'size': 1000,
                            'digest': 'sha256:' + digest, 'browser_download_url': prefix + 'Xray-linux-arm64-v8a.zip'},
                           {'id': 2, 'name': 'Xray-linux-arm64-v8a.zip.dgst', 'state': 'uploaded', 'size': 200,
                            'browser_download_url': prefix + 'Xray-linux-arm64-v8a.zip.dgst'}]}

    normalizer = 'normalize_release("Xray-linux-arm64-v8a.zip";"Xray-linux-arm64-v8a.zip.dgst")'
    check('official-release-normalized', jq(release(), normalizer).returncode == 0)
    for name, mutate in [
        ('foreign-archive-url', lambda r: r['assets'][0].update(browser_download_url='https://example.invalid/x.zip')),
        ('foreign-digest-url', lambda r: r['assets'][1].update(browser_download_url='https://example.invalid/x.dgst')),
        ('duplicate-archive', lambda r: r['assets'].append(copy.deepcopy(r['assets'][0]))),
        ('draft', lambda r: r.update(draft=True)),
        ('wrong-arch', lambda r: r['assets'][0].update(name='Xray-linux-64.zip')),
    ]:
        item = release()
        mutate(item)
        check(name, jq(item, normalizer).returncode != 0)

    context = {'candidateId': 'light-test', 'architecture': 'arm64'}
    positive = dict(context, xrayTag='v26.9.9', archiveSha256=digest, testedAt='2026-09-10T00:00:00Z',
                    evidence='isolated-fixture', status='compatible')
    for name, record, expected in [
        ('own-evidence', positive, 'compatible'),
        ('full-broray-evidence-not-light', dict(positive, candidateId='3.1.0-r09c02'), 'untested'),
        ('different-binary-digest', dict(positive, archiveSha256='b' * 64), 'untested'),
        ('different-architecture', dict(positive, architecture='amd64'), 'untested'),
    ]:
        expression = 'compatibility(' + json.dumps([record]) + ';' + json.dumps(context) + ')'
        result = jq(release(), expression)
        check(name, result.returncode == 0 and json.loads(result.stdout)['status'] == expected, result.stderr)
    records = [positive, dict(positive, status='incompatible', testedAt='2026-09-09T00:00:00Z')]
    result = jq(release(), 'compatibility(' + json.dumps(records) + ';' + json.dumps(context) + ')')
    check('negative-evidence-wins', result.returncode == 0 and json.loads(result.stdout)['status'] == 'incompatible')

    shipped = json.loads((root / 'share/xray-compatibility.json').read_text(encoding='utf-8'))['records']
    rejected = release('v26.2.6')
    rejected['assets'][0]['digest'] = 'sha256:b52d8263453fbd6f4747fd6a1ecf70cd43a664243615dc892ea4674c01b2b5ee'
    shipped_context = {'candidateId': '2.0.0-r1', 'architecture': 'arm64'}
    result = jq(rejected, 'compatibility(' + json.dumps(shipped) + ';' + json.dumps(shipped_context) + ')')
    check('shipped-p89-negative-26.2.6', result.returncode == 0 and json.loads(result.stdout)['status'] == 'incompatible')
    rejected['assets'][0]['digest'] = 'sha256:' + 'c' * 64
    result = jq(rejected, 'compatibility(' + json.dumps(shipped) + ';' + json.dumps(shipped_context) + ')')
    check('shipped-negative-is-exact-archive-bound', result.returncode == 0 and json.loads(result.stdout)['status'] == 'untested')

    with tempfile.TemporaryDirectory(prefix='r0013-xray-selection-') as temporary:
        work = Path(temporary)
        request = work / 'request.json'
        official = work / 'official.json'
        registry = work / 'registry.json'
        env = dict(os.environ, BRORAY_ROOT=shell_path(root), BRORAY_BASE=shell_path(root),
                   BRORAY_XRAY_UPDATE_WORK=shell_path(work), FIXTURE_RELEASE=shell_path(official), FIXTURE_REGISTRY=shell_path(registry))
        env['PATH'] = str(Path(args.jq).parent) + os.pathsep + str(Path(args.shell).parent) + os.pathsep + env.get('PATH', '')
        setup = '. "' + shell_path(lib / 'xray-update.sh') + '"\n' + '''
broray_xray_version_number() { printf '26.7.28\n'; }
broray_xray_context() { printf '{"candidateId":"light-test","architecture":"arm64"}\n'; }
broray_xray_registry() { cat "$FIXTURE_REGISTRY"; }
broray_xray_release_resolve() { cat "$FIXTURE_RELEASE" >"$2"; }
'''
        initial = {'tag': 'v26.9.9', 'currentVersion': '26.7.28', 'archiveSha256': digest,
                   'allowDowngrade': False, 'allowPrerelease': False, 'allowUntested': False}
        cases = [
            ('untested-without-consent', {}, [], release(), False),
            ('untested-confirmed', {'allowUntested': True}, [], release(), True),
            ('tested-stable', {}, [positive], release(), True),
            ('incompatible-cannot-override', {'allowUntested': True}, [dict(positive, status='incompatible')], release(), False),
            ('stale-current-version', {'currentVersion': '26.9.8', 'allowUntested': True}, [], release(), False),
            ('changed-asset-sha', {'archiveSha256': 'b' * 64, 'allowUntested': True}, [], release(), False),
            ('prerelease-needs-separate-consent', {'allowUntested': True}, [], release(prerelease=True), False),
            ('prerelease-confirmed', {'allowUntested': True, 'allowPrerelease': True}, [], release(prerelease=True), True),
            ('downgrade-refused', {'tag': 'v26.6.27', 'allowUntested': True}, [], release('v26.6.27'), False),
            ('downgrade-confirmed', {'tag': 'v26.6.27', 'allowUntested': True, 'allowDowngrade': True}, [], release('v26.6.27'), True),
            ('same-version-reinstall', {'tag': 'v26.7.28', 'allowUntested': True}, [], release('v26.7.28'), True),
            ('caller-url-rejected', {'url': 'https://example.invalid', 'allowUntested': True}, [], release(), False),
            ('string-consent-rejected', {'allowUntested': 'true'}, [], release(), False),
        ]
        for name, changes, evidence, target, expected in cases:
            request.write_text(json.dumps(dict(initial, **changes)), encoding='utf-8')
            official.write_text(json.dumps(target), encoding='utf-8')
            registry.write_text(json.dumps(evidence), encoding='utf-8')
            command = setup + 'broray_xray_selected_check "' + shell_path(request) + '"'
            result = subprocess.run([args.shell, '-c', command], env=env, capture_output=True, text=True, encoding='utf-8', timeout=15)
            check(name, (result.returncode == 0) == expected, (result.stdout, result.stderr))
            payload = json.loads(result.stdout)
            check(name + ':response-contract', payload.get('success') == expected, payload)

    print(json.dumps({'stage': 'R0013', 'revision': 'p8-linux-catalog-and-ui-tests', 'status': 'PASS',
                      'physicalRouterTouched': False, 'testScope': 'real-jq-and-shell-policy-mocked-official-network', 'tests': results}, indent=2))


if __name__ == '__main__':
    main()
