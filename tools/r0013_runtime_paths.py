"""Audited, component-bounded RAM path transforms over exact accepted inputs."""
import hashlib
import json
import re

import r0013_inputs as inputs

ROOT = inputs.REPO / 'packaging/r0013-overlay'
GUARD = b'. "${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/broray-light/lib/runtime-environment.sh" || exit 1\n'


def compile_runtime(app):
    specification = json.loads((ROOT / 'runtime-paths.json').read_bytes())
    assert specification['schemaVersion'] == 1
    result, evidence = dict(app), []
    seen = set()
    for item in specification['files']:
        name = item['path']
        assert name not in seen and name in app
        seen.add(name)
        data, mode = app[name]
        assert hashlib.sha256(data).hexdigest() == item['sourceSha256'], 'runtime transform input changed: '+name
        text = data.decode('utf-8')
        for row in item['replacements']:
            assert row['kind'] in ('literal', 'path-component')
            pattern = re.escape(row['old'])
            if row['kind'] == 'path-component': pattern += r'(?=/|[\s\"\x27;)}]|$)'
            text, count = re.subn(pattern, lambda match: row['new'], text)
            assert count == row['count'] and count > 0, 'runtime transform occurrence changed: '+name
        payload = text.encode('utf-8')
        if item['guard']:
            assert payload.startswith(b'#!/opt/bin/ash\n'), 'unexpected runtime entrypoint format: '+name
            first, rest = payload.split(b'\n', 1)
            payload = first+b'\n'+GUARD+rest
        assert b'/tmp/broray-light/runtime' not in payload and b'$BRL_RAM/runtime' not in payload, 'durable runtime path changed'
        result[name] = (payload, mode)
        evidence.append(dict(path=name, sourceSha256=item['sourceSha256'], sha256=hashlib.sha256(payload).hexdigest(), guard=item['guard']))
    # A single source owns application/updater namespace and lock semantics.
    for name in ('runtime-ram.sh', 'runtime-environment.sh', 'operation-lock.sh'):
        result['lib/'+name] = ((ROOT / 'shared' / name).read_bytes(), 0o755)
    result['bin/broray-runtime-prepare'] = ((ROOT / 'shared/runtime-prepare.sh').read_bytes(), 0o755)
    # This invariant specifically protects the P33 false match of run/runtime.
    for name in ('bin/xray', 'bin/broray-system', 'lib/xray-process.sh'):
        assert result[name] == app[name], 'non-scratch runtime reference changed: '+name
    result['share/lifecycle/RUNTIME-PATH-MANIFEST.json'] = (
        (json.dumps(dict(schemaVersion=1, specificationSha256=hashlib.sha256((ROOT / 'runtime-paths.json').read_bytes()).hexdigest(), files=evidence), sort_keys=True, indent=2)+'\n').encode(), 0o644)
    return result
