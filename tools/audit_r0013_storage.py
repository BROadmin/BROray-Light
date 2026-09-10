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
    parser.add_argument("--scope", choices=["bootstrap", "all"], default="bootstrap")
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
        if args.scope == "all":
            path = "opt/broray-light/releases/2.0.0-r1/app/lib/operation-lock.sh"
            text = data.extractfile(path).read().decode()
            for line in text.splitlines():
                if line.startswith("BRORAY_LIGHT_LOCK_ROOT=") and "/opt/var/lock/" in line:
                    print(json.dumps(dict(stage="R0013", revision="p16-remaining-operational-ram-gate",
                        status="FAIL_FIRST_ERROR", gate="operational-global-lock-ram-only", path=path,
                        evidence=line, reason="Application still creates its default operational lock on persistent /opt",
                        candidateReady=False), indent=2))
                    raise SystemExit(1)
    print(json.dumps(dict(stage="R0013", status="PASS_BOOTSTRAP_PLACEMENT_ONLY", candidateReady=False)))

if __name__ == "__main__":
    main()
