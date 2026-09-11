"""Seal only explicitly named R0013 stage records; never rewrite historical sidecars."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, data):
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", action="append", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument("--next", required=True)
    args = parser.parse_args()
    records = []
    for name in args.record:
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT / "checkpoints/R0013") and path.is_file()
        assert not path.name.endswith(".sha256") and path.name != "SHA256SUMS"
        body = path.read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        sidecar = path.with_name(path.name + ".sha256")
        expected = (digest + "  " + path.name + "\n").encode("ascii")
        if sidecar.exists():
            assert sidecar.read_bytes() == expected, "Refusing to overwrite an existing sidecar"
        else:
            sidecar.write_bytes(expected)
        records.append({"path": path.relative_to(ROOT).as_posix(), "sha256": digest, "bytes": len(body)})
    state_path = ROOT / "project/R0013-STATE.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update(status=args.status, currentRevision=args.revision, nextExactAction=args.next)
    state["latestReleasePreparation"] = records
    write_json(state_path, state)
    entry = {"timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "stage": "R0013", "revision": args.revision, "status": args.status, "records": records, "nextExactAction": args.next}
    with (ROOT / "project/WORKLOG.jsonl").open("ab") as stream:
        stream.write((json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps(entry, ensure_ascii=False))


if __name__ == "__main__":
    main()
