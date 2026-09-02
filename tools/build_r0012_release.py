#!/usr/bin/env python3
"""Deterministic BROray-Light Stable 1.0.0-r3 corrective builder."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import build_r0011_release as legacy


RELEASE_ID = "1.0.0-r3"
CANDIDATE_ID = RELEASE_ID
PACKAGE_VERSION = RELEASE_ID
RELEASE_TAG = f"v{RELEASE_ID}"
STAGE = "R0012"
WEB_ASSET_CACHE_TOKEN = "1.0.0-r3-r0012"
ASSET_BASE_URL = (
    f"https://github.com/BROadmin/BROray-Light/releases/download/{RELEASE_TAG}/"
)
R0011_UPDATER_SIZE = 131458
R0011_UPDATER_SHA256 = (
    "cab97b6efd11a249cada2c7ceff540f732493ea11163fa5377b083ae450723ca"
)


def configure_legacy_builder() -> None:
    legacy.RELEASE_ID = RELEASE_ID
    legacy.CANDIDATE_ID = CANDIDATE_ID
    legacy.PACKAGE_VERSION = PACKAGE_VERSION
    legacy.RELEASE_TAG = RELEASE_TAG
    legacy.STAGE = STAGE
    legacy.WEB_ASSET_CACHE_TOKEN = WEB_ASSET_CACHE_TOKEN
    legacy.ASSET_BASE_URL = ASSET_BASE_URL
    legacy.R0010_UPDATER_SIZE = R0011_UPDATER_SIZE
    legacy.R0010_UPDATER_SHA256 = R0011_UPDATER_SHA256


def replace_documentation_fact(output: Path) -> list[dict[str, object]]:
    manifest_path = output / "RELEASE-MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("stage") != STAGE or manifest.get("releaseId") != RELEASE_ID:
        raise RuntimeError("legacy builder did not accept the R0012 release identity")
    documentation = manifest.get("documentation")
    if not isinstance(documentation, dict):
        raise RuntimeError("release documentation manifest is missing")
    documentation["homeGuideIncluded"] = False
    manifest_path.write_bytes(legacy.base.json_bytes(manifest))

    sums_path = output / "SHA256SUMS"
    names = []
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        _, name = line.split("  ", 1)
        names.append(name)
    artifacts = [legacy.base.artifact(output / name) for name in names]
    sums_path.write_text(
        "\n".join(f"{entry['sha256']}  {entry['path']}" for entry in artifacts) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return artifacts + [legacy.base.artifact(sums_path)]


def main() -> int:
    configure_legacy_builder()
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        result = legacy.main()
    if result != 0:
        return int(result)
    lines = [line for line in captured.getvalue().splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("legacy builder did not report its output directory")
    legacy_summary = json.loads(lines[-1])
    output = Path(str(legacy_summary["output"]))
    artifacts = replace_documentation_fact(output)
    print(json.dumps(
        {"status": "PASS", "stage": STAGE, "output": str(output), "artifacts": artifacts},
        ensure_ascii=False,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
