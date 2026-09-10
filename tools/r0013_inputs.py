"""Accepted r1 inputs plus explicit R0013 overlays; never read dirty R0012 code."""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import subprocess

BASE_COMMIT = '9e5fce9bfa7c82bfc2f2654d80fd3987c5259963'
REPO = Path(__file__).resolve().parents[1]


def git_bytes(path: str) -> bytes:
    return subprocess.check_output(['git', 'show', BASE_COMMIT + ':' + path], cwd=REPO)


def baseline_tree(prefix: str) -> dict[str, tuple[bytes, int]]:
    listing = subprocess.check_output(['git', 'ls-tree', '-r', '-z', BASE_COMMIT, '--', prefix], cwd=REPO)
    entries = {}
    for row in listing.split(b'\0'):
        if not row:
            continue
        metadata, name = row.split(b'\t', 1)
        mode, kind, oid = metadata.decode().split()
        assert kind == 'blob' and mode in ('100644', '100755'), 'unsupported baseline object'
        path = name.decode('utf-8')
        assert path.startswith(prefix + '/'), 'prefix escape'
        entries[path[len(prefix) + 1:]] = (subprocess.check_output(['git', 'cat-file', 'blob', oid], cwd=REPO), int(mode, 8) & 0o777)
    assert entries, 'empty baseline tree'
    return entries


def app_inputs() -> dict[str, tuple[bytes, int]]:
    entries = baseline_tree('src/app')
    for relative, (payload, git_mode) in baseline_tree('packaging/app-overlay').items():
        # r1's builder took payloads from its overlay, but modes from canonical src.
        # Overlay files are often stored as 100644 even for an executable target.
        mode = entries.get(relative, (b'', git_mode))[1]
        entries[relative] = (payload, mode)
    overlay = REPO / 'packaging/r0013-overlay/app'
    for path in sorted(overlay.rglob('*')):
        assert not path.is_symlink(), 'overlay symlink refused'
        if not path.is_file():
            continue
        relative = path.relative_to(overlay).as_posix()
        assert '..' not in PurePosixPath(relative).parts
        mode = entries.get(relative, (b'', 0o755 if path.suffix in ('.sh', '.cgi') or relative.startswith('bin/') else 0o644))[1]
        entries[relative] = (path.read_bytes(), mode)
    return entries


def materialize_app(destination: Path) -> dict[str, str]:
    # Output is an invocation-owned fixture/build directory, not the source tree.
    destination.mkdir(parents=True, exist_ok=False)
    identities = {}
    for relative, (payload, mode) in sorted(app_inputs().items()):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        target.chmod(mode)
        identities[relative] = hashlib.sha256(payload).hexdigest()
    return identities
