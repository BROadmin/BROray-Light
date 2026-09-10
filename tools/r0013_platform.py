"""Explicit external platform payload/rollback contract, accepted r1 Git only."""
import hashlib
import json

import r0013_inputs as inputs

# Ordered activation: keep the updater boot entry last. No path from a manifest
# may expand this set. Public keys/minisign/policy are unchanged trust inputs.
TARGETS = (
    ('opt/etc/init.d/S24broray-light', 'packaging/opkg/S24broray-light'),
    ('opt/libexec/broray-light-web-publish/start-gate.sh', 'packaging/opkg/broray-light-web-start-gate.sh'),
    ('opt/libexec/broray-light-web-publish/network.sh', 'packaging/opkg/broray-light-web-network.sh'),
    ('opt/libexec/broray-light-web-publish/broray-light-web-publish.sh', 'packaging/opkg/broray-light-web-publish.sh'),
    ('opt/libexec/broray-light-updater/runtime-ram.sh', None),
    ('opt/libexec/broray-light-updater/broray-light-updater.sh', 'updater/opt/libexec/broray-light-updater/broray-light-updater.sh'),
    ('opt/etc/init.d/S23broray-light-updater', 'updater/opt/etc/init.d/S23broray-light-updater'),
)
BASE = 'share/lifecycle/platform/'


def payload():
    files, entries = {}, []
    for target, source in TARGETS:
        old = inputs.git_bytes(source) if source else None
        if source:
            override = inputs.REPO / 'packaging/r0013-overlay/system' / source
            new = override.read_bytes() if override.is_file() else old
        else:
            new = (inputs.REPO / 'packaging/r0013-overlay/shared/runtime-ram.sh').read_bytes()
        files[BASE+'new/'+target] = (new, 0o644)
        if old is not None:
            files[BASE+'r1/'+target] = (old, 0o644)
        entries.append(dict(path=target, mode=493,
                            oldSha256=hashlib.sha256(old).hexdigest() if old is not None else None,
                            newSha256=hashlib.sha256(new).hexdigest()))
    manifest = dict(schemaVersion=1, product='BROray-Light', sourceRelease='1.0.0-r1',
                    targetRelease='2.0.0-r1', files=entries)
    files[BASE+'manifest.json'] = ((json.dumps(manifest, sort_keys=True, indent=2)+'\n').encode(), 0o644)
    return files
