#!/usr/bin/env python3
"""Real subscription filesystem transaction with isolated router/Xray boundaries."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from r0013_inputs import materialize_app
from test_r0013_process import shell_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--shell', default=shutil.which('dash') or shutil.which('sh'))
    parser.add_argument('--jq-dir')
    args = parser.parse_args()
    assert args.shell
    dependency_env = dict(os.environ)
    if args.jq_dir:
        dependency_env['PATH'] = args.jq_dir + os.pathsep + dependency_env.get('PATH', '')
    preflight = subprocess.run([args.shell, '-c', 'command -v jq && command -v sha256sum && command -v chmod'],
                               env=dependency_env, capture_output=True, text=True)
    assert preflight.returncode == 0, 'Harness requires jq, sha256sum and chmod; use the declared isolated Linux CI job.'
    results = []
    with tempfile.TemporaryDirectory(prefix='r0013-subscriptions-') as temporary:
        parent = Path(temporary)
        root = parent / 'app'
        hashes = materialize_app(root)
        for directory in ['servers', 'config/system', 'run', 'tmp']:
            (root / directory).mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, BRORAY_ROOT=shell_path(root), BRORAY_BASE=shell_path(root),
                   BRORAY_PROXY_HOST='127.0.0.1', BRORAY_PROXY_PORT='2080',
                   BRORAY_INTERFACE_NDMC='/bin/false', BRORAY_ACTIVE_SERVER_FILE=shell_path(root / 'config/active-server'),
                   TEST_EVENTS=shell_path(parent / 'events'))
        env['PATH'] = os.pathsep.join(filter(None, [args.jq_dir, str(Path(args.shell).parent), env.get('PATH')]))
        stage = parent / 'staged'
        stage.mkdir()
        old = {'schemaVersion': 1, 'id': 'subscription-test-node', 'name': 'Старое имя 🇳🇱', 'protocol': 'vless',
               'address': 'example.invalid', 'port': 443, 'uuid': '11111111-1111-4111-8111-111111111111',
               'network': 'tcp', 'security': 'tls', 'source': {'type': 'subscription', 'subscriptionId': 'test', 'importKey': 'a' * 64}}
        (root / 'config/config.json').write_text('{"inbounds":[{"protocol":"socks","listen":"127.0.0.1","port":2080}]}')
        config_before = (root / 'config/config.json').read_bytes()

        for name, new_name, fail_sync, active, rollback_fail in [
            ('active-rename', 'Новое имя 🇫🇮', False, True, False),
            ('unchanged-name', old['name'], False, True, False),
            ('nonactive-rename', 'Другой сервер', False, False, False),
            ('interface-refusal-rollback', 'Отклонённое имя', True, True, False),
            ('rollback-failure-keeps-backup', 'Восстановление требуется', True, True, True),
        ]:
            previous = json.dumps(old, ensure_ascii=False).encode()
            (root / 'servers/subscription-test-node.json').write_bytes(previous)
            new = copy.deepcopy(old)
            new['name'] = new_name
            (stage / 'subscription-test-node.json').write_text(json.dumps(new, ensure_ascii=False), encoding='utf-8')
            (root / 'config/active-server').write_text(old['id'] + '\n' if active else 'manual-other\n')
            active_before = (root / 'config/active-server').read_bytes()
            (parent / 'events').write_text('')
            command = '. "' + shell_path(root / 'lib/server-subscription-service.sh') + '"\n' + '''
# Only router/Xray effects and schema validation are mocked. File mapping,
# import-key/name/config comparisons, commit, restore and cleanup are real.
broray_server_validate() { return 0; }
broray_interface_sync_description() {
    printf 'sync\n' >>"$TEST_EVENTS"
    [ "$TEST_SYNC_FAILURE" != true ]
}
broray_server_refresh_keenetic_status() { printf 'refresh\n' >>"$TEST_EVENTS"; }
broray_xray_apply_server() { printf 'xray-restart\n' >>"$TEST_EVENTS"; return 1; }
'''
            if rollback_fail:
                command += 'broray_server_subscription_restore_backup() { return 1; }\n'
            command += 'broray_server_subscription_sync test "' + shell_path(stage) + '" true ' + name
            env['TEST_SYNC_FAILURE'] = 'true' if fail_sync else 'false'
            completed = subprocess.run([args.shell, '-c', command], env=env, capture_output=True, text=True, encoding='utf-8', timeout=35)
            events = (parent / 'events').read_text().splitlines()
            expected_failure = active and fail_sync and new_name != old['name']
            assert (completed.returncode != 0) == expected_failure, (name, completed.returncode, completed.stdout, completed.stderr)
            assert 'xray-restart' not in events, (name, events)
            assert (root / 'config/config.json').read_bytes() == config_before, name
            assert (root / 'config/active-server').read_bytes() == active_before, name
            assert not (root / 'run/server-subscription.lock').exists(), name
            if rollback_fail:
                assert 'SUBSCRIPTION_RECOVERY_REQUIRED' in completed.stderr, name
                backups = list((root / 'tmp').glob('server-subscription-sync.*/backup/live/subscription-test-node.json'))
                assert len(backups) == 1 and backups[0].read_bytes() == previous, (name, backups)
            elif expected_failure:
                assert 'ACTIVE_SERVER_CONFLICT' in completed.stderr, name
                assert (root / 'servers/subscription-test-node.json').read_bytes() == previous, name
                assert events == ['sync'], (name, events)
            else:
                response = json.loads(completed.stdout)
                assert json.loads((root / 'servers/subscription-test-node.json').read_text('utf-8'))['name'] == new_name, name
                expected_events = ['sync', 'refresh'] if active and new_name != old['name'] else []
                assert events == expected_events, (name, events)
                if expected_events:
                    assert response['activeServerImpact'] == 'display-name-changed', (name, response)
            if not rollback_fail:
                assert not list((root / 'tmp').glob('server-subscription-sync.*')), name
            results.append({'test': name, 'status': 'PASS'})

    print(json.dumps({'stage': 'R0013', 'revision': 'p6-active-name-linux-harness', 'status': 'PASS',
                      'physicalRouterTouched': False, 'testScope': 'real-filesystem-transactions-mocked-router-boundary',
                      'sourceHashes': {p: h for p, h in hashes.items() if p in ['lib/server-service.sh', 'lib/server-subscription-service.sh', 'lib/server-xray-manager.sh']},
                      'tests': results}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
