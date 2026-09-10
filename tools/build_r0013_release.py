#!/usr/bin/env python3
"""Unsigned R0013 engineering builder: pinned r1 primitives, explicit inputs only.

Signing/publication is a separate acceptance step; these outputs are not ready.
No Python import of the dirty R0012 builders is permitted.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import types
import zipfile
import tarfile

import r0013_inputs as inputs

PUBLIC_VERSION = "2.0.0"
RELEASE_ID = "2.0.0-r1"
TAG = "v2.0.0"
CACHE_TOKEN = "2.0.0-r0013"
ASSET_URL = "https://github.com/BROadmin/BROray-Light/releases/download/" + TAG + "/"
R1_BUILDER_SHA256 = "ce415971eaf98323d7f50a5a1f4d5609710a019cc93570dad4381fcf6665d5ab"
R1_UPDATER_SHA256 = "4983f0fc268a9f19f3e64959fe5f7d8086f26ad907d528ca82ca623f10d9a92a"
PUBLIC_KEY_SHA256 = "b1587b8407f0c0443a361ed29b839319b66912b1b71414bcf31e848c29eab696"
XRAY = {
    "version": "26.9.9",
    "archiveSize": 19837074,
    "archiveSha256": "3e38d72dfc5eb65c91df0e5583e9b6676c32232041da47de6ae73946b526d66c",
    "digestSha256": "992a09e917cd348dcb27e4d3ded119f2ce475cc6dd0698dd4cecd87b12f0b304",
    "binarySize": 35061884,
    "binarySha256": "c1defe42b6db958a97c5e049a02a00a4baaedaca7b51c1c229f0830e288acef5",
}


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def canonical_json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def primitives():
    code = inputs.git_bytes("tools/build_r0009_candidate.py")
    assert sha(code) == R1_BUILDER_SHA256, "accepted r1 builder identity mismatch"
    module = types.ModuleType("r0013_pinned_r1_primitives")
    exec(compile(code, "git:" + inputs.BASE_COMMIT + ":tools/build_r0009_candidate.py", "exec"), module.__dict__)
    module.RELEASE_ID = module.CANDIDATE_ID = RELEASE_ID
    module.PACKAGE_VERSION = PUBLIC_VERSION
    module.XRAY_VERSION = XRAY["version"]
    module.XRAY_BINARY_SHA256 = XRAY["binarySha256"]
    module.XRAY_BINARY_SIZE = XRAY["binarySize"]
    # Python 3.11/3.12 delegate mtime=0 to zlib with a platform OS byte.
    # Normalize that non-payload byte to 255 for Windows/Linux equivalence.
    def deterministic_gzip(payload):
        packed = gzip.compress(payload, compresslevel=9, mtime=0)
        return packed[:9] + b"\xff" + packed[10:]
    module.gzip_deterministic = deterministic_gzip
    return module


def prepared_app():
    app = inputs.app_inputs()
    for relative, (payload, mode) in list(app.items()):
        if relative.startswith("web-new/") and relative.endswith((".js", ".html", ".cgi", ".sh")):
            payload = payload.replace(b"?v=1.0.0-r1-r0010", ("?v=" + CACHE_TOKEN).encode())
            payload = payload.replace(b"?v=1.0.0-r1", ("?v=" + PUBLIC_VERSION).encode())
            assert b"?v=1.0.0-r1" not in payload, "stale versioned navigation"
            app[relative] = (payload, mode)
    build = json.loads(app["web-new/build.json"][0])
    build.update(version=PUBLIC_VERSION, releaseId=RELEASE_ID, candidateId=RELEASE_ID,
                 baseStable="3.1.0-r09", baseCandidate="3.1.0-r09c02")
    app["web-new/build.json"] = (canonical_json(build), 0o644)
    # A fallback seed remains an internal identity, as required by old updaters.
    app["share/defaults/version"] = ((RELEASE_ID + "\n").encode(), 0o644)
    return app


def verify_external(platform, archive_path, digest_path):
    payload = platform.read_bytes()
    assert sha(payload) == R1_UPDATER_SHA256, "published r1 updater platform mismatch"
    base = primitives()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        names = set()
        for entry in archive.getmembers():
            assert base.safe_archive_name(entry.name) and (entry.isfile() or entry.isdir())
            assert entry.name not in names, "duplicate updater member"
            names.add(entry.name)
        minisign = archive.extractfile("opt/libexec/broray-light-updater/minisign").read()
    assert sha(minisign) == base.UPDATER_MINISIGN_SHA256, "minisign trust executable mismatch"
    payload = archive_path.read_bytes()
    assert len(payload) == XRAY["archiveSize"] and sha(payload) == XRAY["archiveSha256"], "Xray archive mismatch"
    digest = digest_path.read_bytes()
    assert sha(digest) == XRAY["digestSha256"], "official Xray digest mismatch"
    assert [line.split()[-1] for line in digest.decode().splitlines()
            if line.lower().startswith("sha2-256")] == [XRAY["archiveSha256"]]
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)) and all(base.safe_archive_name(name) for name in names)
        binary = archive.read("xray")
    assert len(binary) == XRAY["binarySize"] and sha(binary) == XRAY["binarySha256"], "Xray binary mismatch"
    assert binary[:4] == b"\x7fELF" and binary[4] == 2 and binary[18:20] == b"\xb7\x00", "Xray ELF machine mismatch"
    return minisign, binary


def build(output, platform, archive, digest):
    assert not output.exists(), "new independent output directory required"
    base = primitives()
    source = base.verify_source(inputs.REPO)
    app = prepared_app()
    base.source_app_files = lambda repo, modes: [("app/" + name, data, mode) for name, (data, mode) in sorted(app.items())]
    minisign, xray = verify_external(platform, archive, digest)
    rows = []
    for name, (data, mode) in sorted(app.items()):
        rows.append(dict(path="app/" + name, sha256=sha(data), sizeBytes=len(data), mode=oct(mode),
                         origin="R0013-overlay" if (inputs.REPO / "packaging/r0013-overlay/app" / name).is_file()
                         else "accepted-r1-git"))
    with tempfile.TemporaryDirectory(prefix="broray-light-r0013-build-") as temporary:
        tree = Path(temporary)
        for prefix in ("packaging/opkg", "packaging/installer", "updater"):
            for name, (data, mode) in sorted(inputs.baseline_tree(prefix).items()):
                target = tree / prefix / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                target.chmod(mode)
                rows.append(dict(path=prefix + "/" + name, sha256=sha(data), sizeBytes=len(data),
                                 mode=oct(mode), origin="accepted-r1-git"))
        # Only this explicitly named lifecycle/updater overlay can override r1.
        extra_root = inputs.REPO / "packaging/r0013-overlay/system"
        for path in sorted(extra_root.rglob("*")):
            assert not path.is_symlink()
            if not path.is_file():
                continue
            name = path.relative_to(extra_root).as_posix()
            assert name.startswith(("packaging/opkg/", "packaging/installer/", "updater/opt/"))
            data = path.read_bytes()
            target = tree / name
            assert target.is_file(), "new system input needs explicit target contract: " + name
            target.write_bytes(data)
            rows = [row for row in rows if row["path"] != name]
            rows.append(dict(path=name, sha256=sha(data), sizeBytes=len(data), mode="0o755", origin="R0013-overlay"))
        assert sha((tree / "updater/release.pub").read_bytes()) == PUBLIC_KEY_SHA256
        slot, slot_manifest = base.slot_payload(tree, {})
        updater = base.updater_members(tree, minisign)
        outputs = {
            "broray-light-app-" + RELEASE_ID + ".tar.gz": base.build_app_archive(slot),
            "broray-light-updater-platform-5-light1.tar.gz": base.build_updater_archive(updater),
        }
        package_name = "broray-light_" + PUBLIC_VERSION + "_" + base.ARCHITECTURE + ".ipk"
        outputs[package_name] = base.build_ipk(base.build_control_tar(tree), base.build_data_tar(tree, {}, slot, updater, xray))
        package = outputs[package_name]
        outputs["broray-light-install-" + PUBLIC_VERSION + ".sh"] = base.render(
            tree / "packaging/installer/broray-light-install.sh.in", dict(
                PACKAGE_URL=ASSET_URL + package_name, PACKAGE_NAME=package_name,
                PACKAGE_SIZE=str(len(package)), PACKAGE_SHA256=sha(package)))
    app_name = "broray-light-app-" + RELEASE_ID + ".tar.gz"
    outputs["release.json"] = canonical_json({
        "schemaVersion": 1, "product": "BROray-Light", "channel": "stable",
        "candidate": {"releaseId": RELEASE_ID, "candidateId": RELEASE_ID, "version": PUBLIC_VERSION,
            "architecture": base.ARCHITECTURE,
            "bundle": {"filename": app_name, "url": ASSET_URL + app_name,
                       "sizeBytes": len(outputs[app_name]), "sha256": sha(outputs[app_name])},
            "appSlot": {"fileCount": slot_manifest["appFiles"], "logicalBytes": slot_manifest["appLogicalBytes"]}}})
    outputs["INPUT-MANIFEST.json"] = canonical_json({
        "schemaVersion": 1, "stage": "R0013", "baselineCommit": inputs.BASE_COMMIT,
        "primitiveBuilderSha256": R1_BUILDER_SHA256, "canonicalSource": source,
        "transforms": ["versioned web query tokens", "web build metadata", "internal version seed"],
        "files": sorted(rows, key=lambda row: row["path"]), "xray": XRAY,
        "updaterPlatformSha256": R1_UPDATER_SHA256, "signingPublicKeySha256": PUBLIC_KEY_SHA256})
    outputs["ENGINEERING-MANIFEST.json"] = canonical_json({
        "schemaVersion": 1, "stage": "R0013", "status": "UNSIGNED_ENGINEERING_BUILD_NOT_ACCEPTED",
        "publicVersion": PUBLIC_VERSION, "packageVersion": PUBLIC_VERSION, "releaseId": RELEASE_ID,
        "candidateId": RELEASE_ID, "releaseTag": TAG, "candidateReady": False, "releaseReady": False,
        "slot": slot_manifest, "xray": XRAY, "appUpdatePreservesExistingXray": True,
        "pendingGates": ["RAM scratch lifecycle", "full updater transactions", "all WebUI controls",
                         "browser and target", "release signing"],
        "artifacts": [dict(path=name, sizeBytes=len(data), sha256=sha(data)) for name, data in sorted(outputs.items())]})
    outputs["SHA256SUMS"] = "".join(sha(data) + "  " + name + "\n" for name, data in sorted(outputs.items())).encode()
    output.mkdir(parents=True, exist_ok=False)
    for name, data in sorted(outputs.items()):
        path = output / name
        path.write_bytes(data)
        if name.endswith(".sh"):
            path.chmod(0o755)
    return {"status": "ENGINEERING_BUILD_CREATED", "candidateReady": False,
            "artifacts": [dict(path=name, sizeBytes=len(data), sha256=sha(data)) for name, data in sorted(outputs.items())]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--r1-updater", type=Path, required=True)
    parser.add_argument("--xray-archive", type=Path, required=True)
    parser.add_argument("--xray-digest", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output.resolve(), args.r1_updater.resolve(), args.xray_archive.resolve(), args.xray_digest.resolve()), indent=2))


if __name__ == "__main__":
    main()
