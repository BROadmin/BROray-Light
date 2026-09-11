"""Read-only comparison of committed checkpoint bytes with recorded local identities."""
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
items = []
for sidecar in sorted((root / 'checkpoints/R0013').rglob('*.sha256')):
    path = sidecar.with_name(sidecar.name[:-7])
    if not path.is_file():
        continue
    expected = sidecar.read_text().split()[0]
    rel = path.relative_to(root).as_posix()
    result = subprocess.run(['git', 'show', 'HEAD:' + rel], cwd=root, capture_output=True)
    if result.returncode:
        continue
    actual = hashlib.sha256(result.stdout).hexdigest()
    local = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected or local != expected:
        items.append({'path': rel, 'expectedSha256': expected, 'gitSha256': actual, 'localSha256': local,
                      'newlineOnly': result.stdout.replace(b'\r\n', b'\n') == path.read_bytes().replace(b'\r\n', b'\n')})
print(json.dumps({'status': 'PASS' if not items else 'FAIL_COMMITTED_EVIDENCE_BYTES', 'mismatches': items}, indent=2))
