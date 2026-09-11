#!/usr/bin/env python3
"""Bounded manual R0013 target transport; password input is never persisted."""
import argparse
import getpass
import hashlib
import json
import re
from pathlib import Path
import shlex
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "dist/R0013/target-transport-deps"))
import paramiko

HOST = "192.168.1.1"
EXPECTED_KEY = "AAAAC3NzaC1lZDI1NTE5AAAAIELOur87QuBdH9KyZcKMZL+CXsfCbaKklzfI357K8pJp"

def main():
    p = argparse.ArgumentParser()
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--command")
    group.add_argument("--script", type=Path)
    group.add_argument("--get")
    group.add_argument("--put", type=Path)
    p.add_argument("--remote")
    p.add_argument("--output", type=Path)
    p.add_argument("--timeout", type=int, default=120)
    args = p.parse_args()
    if args.output:
        output = args.output.resolve()
        assert output.is_relative_to(REPO / "dist/R0013/private-target"), "private ignored output required"
        assert output.parent.is_dir() and not output.exists(), "refuse overwrite or implicit directory"
    client = paramiko.SSHClient()
    client.load_host_keys(str(Path.home() / ".ssh/known_hosts"))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    password = getpass.getpass("Root password (not saved): ")
    client.connect(HOST, username="root", password=password, look_for_keys=False,
                   allow_agent=False, timeout=8, auth_timeout=15, banner_timeout=15)
    del password
    key = client.get_transport().get_remote_server_key()
    assert key.get_name() == "ssh-ed25519" and key.get_base64() == EXPECTED_KEY, "target identity mismatch"
    if args.put:
        assert args.remote and re.fullmatch(r'/tmp/brl-r13-install-p76\.[A-Za-z0-9]{6}/[A-Za-z0-9_.-]+', args.remote)
        parent = str(Path(args.remote).parent).replace('\\', '/')
        target = shlex.quote(args.remote)
        command = (
            f'umask 077; set -eu; test -d {shlex.quote(parent)}; '
            f'test ! -L {shlex.quote(parent)}; '
            f'test "$(/opt/bin/stat -c %u:%a {shlex.quote(parent)})" = 0:700; '
            f'test ! -e {target}; test ! -L {target}; '
            f'set -C; cat > {target}; /opt/bin/sha256sum {target}'
        )
        payload = args.put.read_bytes()
        assert len(payload) <= 20 * 1024 * 1024
    elif args.get:
        assert args.get.startswith(("/opt/", "/tmp/")) and "\n" not in args.get
        command = "cat -- " + shlex.quote(args.get)
        payload = None
    else:
        command = "/opt/bin/ash -s"
        payload = args.script.read_bytes() if args.script else args.command.encode("utf-8")
    channel = client.get_transport().open_session(timeout=10)
    channel.exec_command(command)
    if payload:
        channel.sendall(payload)
    channel.shutdown_write()
    stdout = bytearray()
    stderr = bytearray()
    deadline = time.monotonic() + args.timeout
    while True:
        if channel.recv_ready():
            stdout.extend(channel.recv(65536))
        if channel.recv_stderr_ready():
            stderr.extend(channel.recv_stderr(65536))
        if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
            break
        if time.monotonic() >= deadline:
            channel.close()
            raise TimeoutError("Remote result uncertain; do not retry mutation without diagnosis")
        time.sleep(0.02)
    rc = channel.recv_exit_status()
    client.close()
    if args.output:
        with output.open("xb") as f:
            f.write(stdout)
        print(json.dumps(dict(exitCode=rc, path=str(output.relative_to(REPO)),
                              bytes=len(stdout), sha256=hashlib.sha256(stdout).hexdigest(),
                              stderr=stderr.decode("utf-8", "replace"))))
    else:
        print(json.dumps(dict(exitCode=rc, stdout=stdout.decode("utf-8", "replace"),
                              stderr=stderr.decode("utf-8", "replace")), ensure_ascii=False))
    sys.exit(rc)

if __name__ == "__main__":
    main()
