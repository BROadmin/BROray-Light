#!/usr/bin/env python3
"""Deterministic R0010 BROray-Light public Stable release builder."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

import build_r0009_candidate as base


RELEASE_TAG = "v1.0.0-r1"
CHANNEL = "stable"
STABLE_INDEX_URL = "https://github.com/BROadmin/BROray-Light/releases/latest/download/release.json"
ASSET_BASE_URL = f"https://github.com/BROadmin/BROray-Light/releases/download/{RELEASE_TAG}/"


def build_signed_release_index(
    repo: Path,
    output: Path,
    app_identity: dict[str, object],
    slot_manifest: dict[str, object],
    minisign_tool: Path,
    signing_key: Path,
) -> tuple[Path, Path]:
    release_index = {
        "schemaVersion": 1,
        "product": "BROray-Light",
        "channel": CHANNEL,
        "candidate": {
            "releaseId": base.RELEASE_ID,
            "candidateId": base.CANDIDATE_ID,
            "architecture": base.ARCHITECTURE,
            "bundle": {
                "filename": app_identity["path"],
                "url": ASSET_BASE_URL + str(app_identity["path"]),
                "sizeBytes": app_identity["sizeBytes"],
                "sha256": app_identity["sha256"],
            },
            "appSlot": {
                "fileCount": slot_manifest["appFiles"],
                "logicalBytes": slot_manifest["appLogicalBytes"],
            },
        },
    }
    release_path = output / "release.json"
    signature_path = output / "release.json.minisig"
    release_path.write_bytes(base.json_bytes(release_index))
    subprocess.run(
        [
            str(minisign_tool),
            "-S",
            "-W",
            "-s",
            str(signing_key),
            "-m",
            str(release_path),
            "-x",
            str(signature_path),
            "-c",
            "BROray-Light Stable",
            "-t",
            f"releaseId={base.RELEASE_ID}",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            str(minisign_tool),
            "-V",
            "-p",
            str(repo / "updater" / "release.pub"),
            "-m",
            str(release_path),
            "-x",
            str(signature_path),
        ],
        check=True,
        capture_output=True,
    )
    return release_path, signature_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--updater-platform", type=Path, required=True)
    parser.add_argument("--xray-archive", type=Path, required=True)
    parser.add_argument("--xray-digest", type=Path, required=True)
    parser.add_argument("--minisign-tool", type=Path, required=True)
    parser.add_argument("--signing-key", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    source_identity = base.verify_source(repo)
    modes = base.git_modes(repo)
    minisign, xray = base.verify_external_inputs(
        args.updater_platform.resolve(), args.xray_archive.resolve(), args.xray_digest.resolve()
    )
    slot_members, slot_manifest = base.slot_payload(repo, modes)
    app_payload = base.build_app_archive(slot_members)
    updater_members = base.updater_members(repo, minisign)
    updater_payload = base.build_updater_archive(updater_members)
    data_tar = base.build_data_tar(repo, modes, slot_members, updater_members, xray)
    control_tar = base.build_control_tar(repo)
    ipk_payload = base.build_ipk(control_tar, data_tar)

    app_path = output / f"broray-light-app-{base.CANDIDATE_ID}.tar.gz"
    updater_path = output / "broray-light-updater-platform-5-light1.tar.gz"
    package_name = f"broray-light_{base.PACKAGE_VERSION}_{base.ARCHITECTURE}.ipk"
    package_path = output / package_name
    app_path.write_bytes(app_payload)
    updater_path.write_bytes(updater_payload)
    package_path.write_bytes(ipk_payload)

    package_identity = base.artifact(package_path)
    installer_path = output / f"broray-light-install-{base.CANDIDATE_ID}.sh"
    installer_path.write_bytes(
        base.render(
            repo / "packaging/installer/broray-light-install.sh.in",
            {
                "PACKAGE_URL": ASSET_BASE_URL + package_name,
                "PACKAGE_SIZE": str(package_identity["sizeBytes"]),
                "PACKAGE_SHA256": str(package_identity["sha256"]),
                "PACKAGE_NAME": package_name,
            },
        )
    )
    os.chmod(installer_path, 0o755)

    app_identity = base.artifact(app_path)
    release_path, signature_path = build_signed_release_index(
        repo,
        output,
        app_identity,
        slot_manifest,
        args.minisign_tool.resolve(),
        args.signing_key.resolve(),
    )
    artifacts = [
        base.artifact(path)
        for path in (app_path, updater_path, package_path, installer_path, release_path, signature_path)
    ]
    manifest = {
        "schemaVersion": 1,
        "stage": "R0010",
        "product": "BROray-Light",
        "releaseId": base.RELEASE_ID,
        "candidateId": base.CANDIDATE_ID,
        "releaseIntent": "PUBLIC_STABLE",
        "distribution": {
            "repository": "BROadmin/BROray-Light",
            "tag": RELEASE_TAG,
            "channel": CHANNEL,
            "stableIndexUrl": STABLE_INDEX_URL,
            "assetBaseUrl": ASSET_BASE_URL,
        },
        "signedReleaseIndex": {
            "index": release_path.name,
            "signature": signature_path.name,
            "publicKey": "updater/release.pub",
        },
        "source": source_identity,
        "slot": slot_manifest,
        "updater": {
            "engine": "broray-light-updater/5-light1",
            "service": "S23broray-light-updater",
            "defaultIndexUrl": STABLE_INDEX_URL,
        },
        "webPublication": {
            "contract": "broray-light-keendns-web-publish/1",
            "proxyName": "brolight",
            "upstreamPort": 8080,
            "policySha256": "e3e0e68b10ef69fce1c504f2689d1ecbd3f8b6b78ee6e7ab03d8ea73d63607dc",
            "ownership": "exact-receipt-fail-closed",
        },
        "xray": {
            "version": base.XRAY_VERSION,
            "architecture": base.ARCHITECTURE,
            "binarySizeBytes": base.XRAY_BINARY_SIZE,
            "binarySha256": base.XRAY_BINARY_SHA256,
            "installPath": "/opt/broray-light/runtime/xray",
        },
        "artifacts": artifacts,
    }
    manifest_path = output / "RELEASE-MANIFEST.json"
    manifest_path.write_bytes(base.json_bytes(manifest))
    artifacts.append(base.artifact(manifest_path))
    sums_path = output / "SHA256SUMS"
    sums_path.write_text(
        "\n".join(f"{entry['sha256']}  {entry['path']}" for entry in artifacts) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    summary = {"status": "PASS", "output": str(output), "artifacts": artifacts + [base.artifact(sums_path)]}
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
