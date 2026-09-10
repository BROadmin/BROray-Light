#!/usr/bin/env python3
"""Read-only, hash-pinned comparison of the two published BROray app slots."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import tarfile
from pathlib import Path, PurePosixPath

PINS = {
    "3.0.0-r23c02": "69679f6d7339b856faf28f69cb1800254984e5400201fe97247011ab166c3f85",
    "3.1.0-r09c02": "635e905d0fb31aff84cd92026dfed21ad204ea45c8d0a5562fecb248178b32e8",
}


def read_archive(path: Path, expected: str) -> dict[str, tuple[bytes, int]]:
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"archive identity mismatch: {path.name}")
    files = {}
    names = set()
    total = 0
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            name = member.name.rstrip("/")
            parts = PurePosixPath(name).parts
            if not name or member.name.startswith("/") or ".." in parts or "\\" in name:
                raise ValueError(f"unsafe member: {member.name!r}")
            if name in names:
                raise ValueError(f"duplicate member: {name}")
            names.add(name)
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError(f"non-regular member: {name}")
            total += member.size
            if member.size > 16 * 1024 * 1024 or total > 32 * 1024 * 1024:
                raise ValueError("donor size limit exceeded")
            stream = archive.extractfile(member)
            assert stream is not None
            payload = stream.read()
            if len(payload) != member.size:
                raise ValueError(f"short member: {name}")
            files[name] = (payload, member.mode)
    return files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--member")
    parser.add_argument("--diff")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    old = read_archive(repo / "dist/R0013/donor-3.0.0-r23/broray-app-3.0.0-r23c02.tar.gz", PINS["3.0.0-r23c02"])
    new = read_archive(repo / "dist/R0013/donor-3.1.0-r09/broray-app-3.1.0-r09c02.tar.gz", PINS["3.1.0-r09c02"])
    if args.member:
        print(new[args.member][0].decode("utf-8"))
        return
    if args.diff:
        print("".join(difflib.unified_diff(
            old.get(args.diff, (b"", 0))[0].decode("utf-8").splitlines(True),
            new.get(args.diff, (b"", 0))[0].decode("utf-8").splitlines(True),
            fromfile="r23/" + args.diff, tofile="r09/" + args.diff,
        )))
        return
    treatment = {r["path"]: r["treatment"] for r in json.loads((repo / "project/R23-DONOR-FILE-TREATMENT.json").read_text("utf-8"))["records"]}
    records = []
    for name in sorted(old.keys() | new.keys()):
        before, after = old.get(name), new.get(name)
        if before == after:
            continue
        records.append({
            "path": name,
            "change": "added" if before is None else "removed" if after is None else "modified",
            "r0008Treatment": treatment.get(name, "NEW_REQUIRES_REVIEW"),
            "beforeSha256": hashlib.sha256(before[0]).hexdigest() if before else None,
            "afterSha256": hashlib.sha256(after[0]).hexdigest() if after else None,
            "afterBytes": len(after[0]) if after else 0,
        })
    print(json.dumps({
        "schemaVersion": 1, "stage": "R0013", "archiveSafety": "PASS",
        "from": {"candidate": "3.0.0-r23c02", "sha256": PINS["3.0.0-r23c02"], "files": len(old)},
        "to": {"candidate": "3.1.0-r09c02", "sha256": PINS["3.1.0-r09c02"], "files": len(new)},
        "unchanged": sum(old.get(n) == v for n, v in new.items()), "changes": records,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
