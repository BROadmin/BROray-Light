#!/usr/bin/env python3
"""Execute the published r1 updater's read-only release comparator."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--shell', required=True)
    parser.add_argument('--r1-updater', type=Path, required=True)
    parser.add_argument('--release-id', required=True)
    args = parser.parse_args()
    payload = args.r1_updater.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == '4983f0fc268a9f19f3e64959fe5f7d8086f26ad907d528ca82ca623f10d9a92a'
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as archive:
        script = archive.extractfile('opt/libexec/broray-light-updater/broray-light-updater.sh').read()
    results = []
    for installed, available, expected in [('1.0.0-r1', args.release_id, 'newer'),
        (args.release_id, args.release_id, 'equal'), (args.release_id, '1.0.0-r1', 'older')]:
        result = subprocess.run([args.shell, '-s', '--', 'relation', installed, available], input=script, capture_output=True, timeout=10)
        actual = result.stdout.decode().strip()
        record = {'installed': installed, 'available': available, 'expected': expected, 'actual': actual,
                  'status': 'PASS' if actual == expected and result.returncode == 0 else 'FAIL'}
        results.append(record)
        if record['status'] != 'PASS':
            print(json.dumps({'stage': 'R0013', 'status': 'FAIL_FIRST_ERROR', 'tests': results, 'updaterSha256': hashlib.sha256(script).hexdigest()}, indent=2))
            raise SystemExit(1)
    print(json.dumps({'stage': 'R0013', 'status': 'PASS', 'tests': results, 'updaterSha256': hashlib.sha256(script).hexdigest()}, indent=2))


if __name__ == '__main__':
    main()
