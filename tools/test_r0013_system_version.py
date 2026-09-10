#!/usr/bin/env python3
"""Real system-info shell/jq: slot public version, independent of updater config."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import r0013_inputs as inputs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shell", required=True)
    args = parser.parse_args()
    assert shutil.which("jq"), "Linux jq is required"
    script = inputs.app_inputs()["bin/broray-system"][0]
    with tempfile.TemporaryDirectory(prefix="r0013-version-") as temporary:
        root = Path(temporary)
        (root / "current").mkdir()
        (root / "config").mkdir()
        (root / "config/version").write_text("2.0.0-r1\n")
        metadata = dict(product="BROray-Light", version="2.0.0", releaseId="2.0.0-r1", candidateId="2.0.0-r1")
        env = dict(os.environ, BRORAY_ROOT=str(root))
        def invoke():
            return subprocess.run([args.shell, "-s", "--", "info"], input=script, env=env,
                                  capture_output=True, timeout=10)
        def save(value):
            (root / "current/release.json").write_text(json.dumps(value))
        save(metadata)
        result = invoke()
        assert result.returncode == 0, result.stderr.decode()
        data = json.loads(result.stdout)
        assert data["version"] == "2.0.0" and data["releaseId"] == "2.0.0-r1"
        assert data["xrayVersion"] is None, "missing runtime must not invent a version"
        (root / "config/version").write_text("stale-value\n")
        assert json.loads(invoke().stdout)["version"] == "2.0.0"
        save(dict(metadata, product="BROray"))
        assert invoke().returncode != 0, "foreign product must fail closed"
        (root / "current/release.json").unlink()
        assert invoke().returncode != 0, "missing slot metadata must not claim installed version"
    print(json.dumps(dict(stage="R0013", revision="p13", status="PASS",
        tests=["public-vs-internal-version", "missing-xray-not-invented", "slot-authoritative",
               "foreign-product-refusal", "missing-metadata-refusal"])))

if __name__ == "__main__":
    main()
