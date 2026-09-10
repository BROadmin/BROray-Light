#!/usr/bin/env python3
"""Fail-fast RAM placement gate against the produced package, not intentions."""
import argparse
import io
import json
import tarfile
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    args = parser.parse_args()
    package = args.build / "broray-light_2.0.0_aarch64-3.10.ipk"
    with tarfile.open(package, "r:gz") as outer:
        payload = outer.extractfile("./data.tar.gz").read()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as data:
        for member in data:
            if member.isfile() and member.name.startswith("opt/libexec/broray-light-bootstrap/"):
                print(json.dumps(dict(stage="R0013", revision="p14-protected-ram-lifecycle-audit",
                    status="FAIL_FIRST_ERROR", gate="clean-bootstrap-ram-only", path=member.name,
                    sizeBytes=member.size,
                    reason="Temporary clean-bootstrap input is packaged on persistent /opt",
                    candidateReady=False), indent=2))
                raise SystemExit(1)
    print(json.dumps(dict(stage="R0013", status="PASS_BOOTSTRAP_PLACEMENT_ONLY", candidateReady=False)))

if __name__ == "__main__":
    main()
