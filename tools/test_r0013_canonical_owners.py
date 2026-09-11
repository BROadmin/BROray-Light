"""Regression for real P95 overlap theft; exact dedup CLI, no router/network."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from r0013_inputs import materialize_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--shell', default='/bin/dash')
    parser.add_argument('--busybox', action='store_true')
    args = parser.parse_args()
    assert os.name == 'posix'
    records = []
    with tempfile.TemporaryDirectory(prefix='r0013-canonical-owner-') as name:
        root = Path(name) / 'app'
        materialize_app(root)
        for relative in ('servers', 'config/system', 'config/subscriptions', 'tmp', 'run', 'backup', 'logs'):
            (root / relative).mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, BRORAY_ROOT=str(root))
        config = root / 'config/system/server-auto-switch.json'
        owner_map = root / 'config/system/server-canonical-owners.json'
        active = root / 'config/active-server'
        old = {'id':'subscription-z-old', 'identityKey':'a'*64, 'source':{'type':'subscription','subscriptionId':'z-old','importKey':'b'*64}}
        new = {'id':'subscription-a-new', 'identityKey':'a'*64, 'source':{'type':'subscription','subscriptionId':'a-new','importKey':'b'*64}}
        manual = {'id':'manual-later', 'identityKey':'a'*64, 'source':{'type':'manual','importKey':'b'*64}}

        def write_node(item):
            (root / 'servers' / (item['id']+'.json')).write_text(json.dumps(item))

        def run(expected=True):
            command = [args.shell] + (['ash'] if args.busybox else []) + [str(root/'bin/broray-subscriptions'),'deduplicate']
            result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=20)
            assert (result.returncode == 0) == expected, (result.returncode,result.stdout,result.stderr)
            return sorted(p.stem for p in (root/'servers').glob('*.json'))

        def passed(name):
            records.append({'test':name,'status':'PASS'})

        write_node(old)
        config.write_text(json.dumps({'orderedServerIds':[old['id']],'excludedServerIds':[old['id']]}))
        assert run() == [old['id']]
        seeded = owner_map.read_bytes()
        assert json.loads(seeded)['identity'][old['identityKey']] == old['id']
        passed('seed-map-from-existing-catalog')
        write_node(new)
        assert run() == [old['id']]
        assert json.loads(config.read_text()) == {'orderedServerIds':[old['id']],'excludedServerIds':[old['id']]}
        assert owner_map.read_bytes() == seeded
        passed('lexically-earlier-new-source-does-not-steal-owner-order-or-exclusion')
        # Repeated overlapping source refresh must not change the election.
        write_node(new)
        assert run() == [old['id']]
        passed('overlapping-refresh-retains-canonical-owner')
        write_node(manual)
        assert run() == [manual['id']]
        passed('manual-still-outranks-subscription')
        write_node(new)
        active.write_text(new['id']+'\n')
        assert run() == [new['id']]
        passed('active-still-outranks-manual')
        write_node(old)
        owner_map.write_text('{"schemaVersion":1,"identity":[],"import":{}}')
        before = {p.name:p.read_bytes() for p in (root/'servers').glob('*.json')}
        run(False)
        assert before == {p.name:p.read_bytes() for p in (root/'servers').glob('*.json')}
        passed('malformed-map-fails-before-server-deletion')
        owner_map.unlink()
        outside = root / 'outside.json'
        outside.write_bytes(seeded)
        owner_map.symlink_to(outside)
        run(False)
        assert outside.read_bytes() == seeded and before == {p.name:p.read_bytes() for p in (root/'servers').glob('*.json')}
        passed('symlink-map-fails-before-server-or-target-write')
    print(json.dumps({'schemaVersion':1,'revision':'p97-canonical-owners-v1','status':'PASS','tests':records,'scope':'exact dedup CLI, isolated filesystem; no target or network'},indent=2))


if __name__ == '__main__':
    main()
