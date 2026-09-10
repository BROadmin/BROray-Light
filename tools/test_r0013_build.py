#!/usr/bin/env python3
"""Read-only structural/version tests of the actual R0013 engineering artifacts."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

from build_r0013_release import PUBLIC_VERSION, RELEASE_ID, TAG, XRAY, CACHE_TOKEN, UPDATER_PLATFORM_NAME

REPO = Path(__file__).resolve().parents[1]

def sha(payload):
    return hashlib.sha256(payload).hexdigest()

def files(payload):
    result = {}
    names = set()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            assert not path.is_absolute() and ".." not in path.parts and "\\" not in member.name
            assert member.name not in names, "duplicate archive member"
            assert member.isfile() or member.isdir(), "non-regular archive member"
            assert member.uid == 0 and member.gid == 0 and member.mtime == 0
            names.add(member.name)
            if member.isfile():
                result[member.name.removeprefix("./")] = (archive.extractfile(member).read(), member.mode)
    return result

def sums(payload, entries):
    for line in payload.decode().splitlines():
        expected, name = line.split("  ", 1)
        assert name in entries, "missing manifest member: " + name
        assert sha(entries[name][0]) == expected, "manifest mismatch: " + name

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--r1-updater", type=Path)
    args = parser.parse_args()
    root = args.build
    tests = []
    def passed(name):
        tests.append(dict(test=name, status="PASS"))
    entries = {path.name: (path.read_bytes(), 0) for path in root.iterdir() if path.is_file()}
    sums(entries["SHA256SUMS"][0], entries)
    passed("outer-sha256-manifest")
    slot = files(entries["broray-light-app-" + RELEASE_ID + ".tar.gz"][0])
    sums(slot["APP-SHA256SUMS"][0], slot)
    metadata = json.loads(slot["release.json"][0])
    manifest = json.loads(slot["SLOT-MANIFEST.json"][0])
    assert metadata["version"] == PUBLIC_VERSION and metadata["releaseId"] == RELEASE_ID
    assert metadata["candidateId"] == RELEASE_ID
    app = {p: row for p, row in slot.items() if p.startswith("app/")}
    assert len(app) == manifest["appFiles"]
    assert sum(len(row[0]) for row in app.values()) == manifest["appLogicalBytes"]
    assert sha(slot["APP-SHA256SUMS"][0]) == manifest["appSha256SumsSha256"]
    passed("slot-version-internal-identity-and-all-file-hashes")
    build = json.loads(slot["app/web-new/build.json"][0])
    assert build["version"] == PUBLIC_VERSION and build["releaseId"] == RELEASE_ID
    assert build["pages"] == ["home", "servers", "subscriptions"]
    for path, (payload, mode) in app.items():
        if path.startswith("app/web-new/") and path.endswith((".js", ".html", ".cgi", ".sh")):
            assert b"?v=1.0.0-r1" not in payload, "stale cache/navigation: " + path
        if path.endswith(".cgi") or path.startswith("app/bin/"):
            assert mode == 0o755, "not executable: " + path
    for page in ("index", "home", "servers", "subscriptions"):
        assert ("?v=" + CACHE_TOKEN).encode() in app["app/web-new/" + page + ".html"][0]
    input_manifest = json.loads(entries["INPUT-MANIFEST.json"][0])
    for row in input_manifest["files"]:
        if row["path"].startswith("app/"):
            payload, mode = app[row["path"]]
            assert mode == int(row["mode"], 8) and sha(payload) == row["sha256"]
    passed("three-pages-entrypoint-modes-complete-mode-manifest-and-versioned-assets")
    index = json.loads(entries["release.json"][0])
    assert index["candidate"]["releaseId"] == RELEASE_ID
    assert index["candidate"]["version"] == PUBLIC_VERSION
    bundle = index["candidate"]["bundle"]
    assert sha(entries[bundle["filename"]][0]) == bundle["sha256"]
    assert len(entries[bundle["filename"]][0]) == bundle["sizeBytes"]
    assert "/download/" + TAG + "/" in bundle["url"]
    passed("legacy-compatible-unsigned-index-contract")
    package = files(entries["broray-light_" + PUBLIC_VERSION + "_aarch64-3.10.ipk"][0])
    assert package["debian-binary"][0] == b"2.0\n"
    control = files(package["control.tar.gz"][0])
    assert ("Version: " + PUBLIC_VERSION + "\n").encode() in control["control"][0]
    data = files(package["data.tar.gz"][0])
    prefix = "opt/broray-light/releases/" + RELEASE_ID + "/"
    assert {p[len(prefix):]: row for p, row in data.items() if p.startswith(prefix)} == slot
    bootstrap = data["tmp/broray-light-bootstrap/xray-" + XRAY["version"]][0]
    assert not any(name.startswith("opt/libexec/broray-light-bootstrap/") for name in data)
    assert len(bootstrap) == XRAY["binarySize"] and sha(bootstrap) == XRAY["binarySha256"]
    passed("ipk-version-slot-and-exact-clean-xray")
    updater = files(entries[UPDATER_PLATFORM_NAME][0])
    sums(updater["SHA256SUMS"][0], updater)
    for path, row in updater.items():
        if path.startswith('opt/'):
            assert data[path] == row, 'IPK/platform updater mismatch: ' + path
    if args.r1_updater:
        old = files(args.r1_updater.read_bytes())
        changes = {
            'opt/libexec/broray-light-updater/broray-light-updater.sh': 'system/updater/opt/libexec/broray-light-updater/broray-light-updater.sh',
            'opt/libexec/broray-light-updater/runtime-ram.sh': 'shared/runtime-ram.sh',
            'opt/etc/init.d/S23broray-light-updater': 'system/updater/opt/etc/init.d/S23broray-light-updater',
        }
        assert set(updater) == set(old) | set(changes), 'unexpected updater platform member'
        for path, row in updater.items():
            if path in changes:
                expected = (REPO / 'packaging/r0013-overlay' / changes[path]).read_bytes()
                assert row == (expected, 0o755), 'unreviewed updater port payload/mode: ' + path
            elif path != 'SHA256SUMS':
                assert row == old[path], 'r1 trust/wrapper payload changed: ' + path
        assert input_manifest['updaterPlatformSha256'] == sha(entries[UPDATER_PLATFORM_NAME][0])
        passed("explicit-ram-updater-port-with-r1-trust-and-wrapper-preservation")
    if args.compare:
        other = {p.name: (p.read_bytes(), 0) for p in args.compare.iterdir() if p.is_file()}
        assert entries == other, "independent engineering build bytes differ"
        passed("independent-process-build-byte-reproducibility")
    print(json.dumps(dict(stage="R0013", revision="p23-updater-platform-package-integration", status="PASS",
                         candidateReady=False, scope="structural only; not lifecycle acceptance", tests=tests), indent=2))

if __name__ == "__main__":
    main()
