#!/usr/bin/env python3
"""R0009 isolated-root acceptance harness (no router or production mutation)."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

RELEASE_ID = "0.1.0-r9"
CANDIDATE_ID = "0.1.0-r0009c04"
XRAY_SHA256 = "4b8af237444801bf17b3dc10a1c5c24581fbe3d433eba3d78c6c3a0da1df56fc"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def parse_ipk(path: Path) -> dict[str, bytes]:
    with tarfile.open(path, "r:gz") as archive:
        entries = archive.getmembers()
        expected = [".", "./debian-binary", "./data.tar.gz", "./control.tar.gz"]
        if [entry.name for entry in entries] != expected:
            raise RuntimeError("invalid Entware ipk member order or names")
        if not entries[0].isdir() or any(not entry.isfile() for entry in entries[1:]):
            raise RuntimeError("invalid Entware ipk member types")
        members: dict[str, bytes] = {}
        for entry in entries[1:]:
            extracted = archive.extractfile(entry)
            if extracted is None:
                raise RuntimeError(f"missing Entware ipk member payload: {entry.name}")
            members[entry.name.removeprefix("./")] = extracted.read()
    if members["debian-binary"] != b"2.0\n":
        raise RuntimeError("invalid Entware ipk debian-binary contract")
    return members


def safe_member(member: tarfile.TarInfo) -> bool:
    path = PurePosixPath(member.name)
    return bool(member.name) and not path.is_absolute() and ".." not in path.parts and (member.isfile() or member.isdir())


def extract_tar(payload: bytes, destination: Path) -> None:
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for member in archive.getmembers():
            if not safe_member(member):
                raise RuntimeError(f"unsafe package member: {member.name}")
            target = destination / PurePosixPath(member.name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise RuntimeError(f"missing package member data: {member.name}")
                target.write_bytes(source.read())
                os.chmod(target, member.mode)


def posix(path: Path) -> str:
    return path.resolve().as_posix()


def run(command: list[str], *, env: dict[str, str], expected: int = 0, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, env=env, cwd=cwd, text=True, capture_output=True)
    if result.returncode != expected:
        raise RuntimeError(
            f"command failed rc={result.returncode} expected={expected}: {command}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def write_shim(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8", newline="\n")
    os.chmod(path, 0o755)


def prepare_tools(root: Path, dash: Path, jq: Path, minisign: Path, python: Path) -> tuple[dict[str, str], Path]:
    tools = root / "test-tools"
    tools.mkdir()
    helper = tools / "fs_helper.py"
    helper.write_text(
        "import hashlib, os, pathlib, shutil, subprocess, sys\n"
        "op=sys.argv[1]; args=sys.argv[2:]\n"
        "if op=='ln':\n"
        " target,link=args[-2],pathlib.Path(args[-1]); link=link.resolve(); target_path=(link.parent/target).resolve() if not pathlib.Path(target).is_absolute() else pathlib.Path(target)\n"
        " result=subprocess.run(['cmd.exe','/d','/c','mklink','/J',str(link),str(target_path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
        " if result.returncode: raise SystemExit(result.returncode)\n"
        " pathlib.Path(str(link)+'.__target').write_text(target,encoding='utf-8')\n"
        "elif op=='readlink':\n"
        " link=pathlib.Path(args[-1]).absolute(); side=pathlib.Path(str(link)+'.__target')\n"
        " if side.exists(): print(side.read_text(encoding='utf-8'),end='')\n"
        " else: raise SystemExit(1)\n"
        "elif op=='sha256sum':\n"
        " if args and args[0]=='-c':\n"
        "  failed=0\n"
        "  for line in pathlib.Path(args[1]).read_text(encoding='utf-8').splitlines():\n"
        "   expected,name=line.split('  ',1); actual=hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest(); print(f'{name}: '+('OK' if actual==expected else 'FAILED')); failed += actual!=expected\n"
        "  raise SystemExit(1 if failed else 0)\n"
        " for name in args:\n"
        "  print(hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()+'  '+name)\n"
        "elif op=='chmod':\n"
        " raise SystemExit(0)\n"
        "elif op=='mv':\n"
        " flags=[x for x in args if x.startswith('-')]; values=[x for x in args if not x.startswith('-')]; source=pathlib.Path(values[-2]).absolute(); destination=pathlib.Path(values[-1]).absolute(); side=pathlib.Path(str(source)+'.__target')\n"
        " if side.exists():\n"
        "  if destination.exists(): subprocess.run(['cmd.exe','/d','/c','rmdir',str(destination)],check=True,stdout=subprocess.DEVNULL)\n"
        "  os.rename(source,destination); os.replace(side,pathlib.Path(str(destination)+'.__target'))\n"
        " elif any('f' in flag[1:] for flag in flags): os.replace(source,destination)\n"
        " else: shutil.move(str(source),str(destination))\n"
        ,
        encoding="utf-8",
        newline="\n",
    )
    py = posix(python)
    write_shim(tools / "ln", f"#!/bin/sh\nexec '{py}' '{posix(helper)}' ln \"$@\"\n")
    write_shim(tools / "readlink", f"#!/bin/sh\nexec '{py}' '{posix(helper)}' readlink \"$@\"\n")
    write_shim(tools / "sha256sum", f"#!/bin/sh\nexec '{py}' '{posix(helper)}' sha256sum \"$@\"\n")
    write_shim(tools / "chmod", f"#!/bin/sh\nexec '{py}' '{posix(helper)}' chmod \"$@\"\n")
    write_shim(tools / "mv", f"#!/bin/sh\nexec '{py}' '{posix(helper)}' mv \"$@\"\n")
    shutil.copy2(jq, tools / "jq-native.exe")
    write_shim(tools / "jq", f"#!/bin/sh\nexec '{posix(tools / 'jq-native.exe')}' --binary \"$@\"\n")
    shutil.copy2(Path(os.environ["SystemRoot"]) / "System32/curl.exe", tools / "curl.exe")
    shutil.copy2(Path(os.environ["SystemRoot"]) / "System32/tar.exe", tools / "tar.exe")
    git_bin = dash.parent
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join([str(tools), str(git_bin), str(Path(os.environ["SystemRoot"]) / "System32")])
    environment["BRORAY_LIGHT_SIGNATURE_BIN"] = posix(minisign)
    return environment, tools


def remove_junction(path: Path) -> None:
    if path.exists() or path.is_symlink():
        subprocess.run(["cmd.exe", "/d", "/c", "rmdir", str(path)], check=True, stdout=subprocess.DEVNULL)


def make_junction(path: Path, target: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(path), str(target)], check=True, stdout=subprocess.DEVNULL)


def set_current(app_root: Path, release: str) -> None:
    current = app_root / "current"
    remove_junction(current)
    make_junction(current, app_root / "releases" / release)


def clone_slot(app_root: Path, source_release: str, target_release: str) -> None:
    source = app_root / "releases" / source_release
    target = app_root / "releases" / target_release
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    release_path = target / "release.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    release["releaseId"] = target_release
    release["candidateId"] = target_release + "c-test"
    json_write(release_path, release)


def signed_index(
    directory: Path,
    app_bundle: Path,
    app_files: int,
    app_bytes: int,
    minisign: Path,
    secret_key: Path,
    *,
    sha_override: str | None = None,
    size_override: int | None = None,
) -> Path:
    index = directory / "release.json"
    value = {
        "schemaVersion": 1,
        "product": "BROray-Light",
        "channel": "internal-r0009",
        "candidate": {
            "releaseId": RELEASE_ID,
            "candidateId": CANDIDATE_ID,
            "architecture": "aarch64-3.10",
            "bundle": {
                "url": app_bundle.resolve().as_uri(),
                "sizeBytes": size_override if size_override is not None else app_bundle.stat().st_size,
                "sha256": sha_override or sha256(app_bundle),
            },
            "appSlot": {"fileCount": app_files, "logicalBytes": app_bytes},
        },
    }
    json_write(index, value)
    signature = Path(str(index) + ".minisig")
    subprocess.run(
        [str(minisign), "-S", "-W", "-s", str(secret_key), "-m", str(index), "-x", str(signature),
         "-c", "BROray-Light R0009 internal", "-t", "releaseId=0.1.0-r9"],
        check=True,
        capture_output=True,
        text=True,
    )
    return index


def malicious_bundle(path: Path) -> None:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.GNU_FORMAT) as archive:
        payload = b"escape\n"
        info = tarfile.TarInfo("../escape")
        info.size = len(payload)
        info.mode = 0o644
        info.mtime = 0
        archive.addfile(info, io.BytesIO(payload))
    path.write_bytes(gzip.compress(stream.getvalue(), compresslevel=9, mtime=0))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--dash", type=Path, required=True)
    parser.add_argument("--jq", type=Path, required=True)
    parser.add_argument("--minisign", type=Path, required=True)
    parser.add_argument("--signing-key", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--keep-root", type=Path)
    args = parser.parse_args()

    if args.keep_root:
        root = args.keep_root.resolve()
        root.mkdir(parents=True, exist_ok=False)
    else:
        root = Path(tempfile.mkdtemp(prefix="broray-light-r0009-isolated-"))
    results: dict[str, object] = {"schemaVersion": 1, "isolatedRoot": str(root), "gates": {}}
    gates: dict[str, str] = results["gates"]  # type: ignore[assignment]

    package = next(args.build.glob("broray-light_*.ipk"))
    app_bundle = next(args.build.glob("broray-light-app-*.tar.gz"))
    members = parse_ipk(package)
    system_root = root / "system"
    control_root = root / "control"
    extract_tar(members["data.tar.gz"], system_root)
    extract_tar(members["control.tar.gz"], control_root)
    gates["packageCarrierLayout"] = "PASS"

    primary_init = (system_root / "opt/etc/init.d/S24broray-light").read_text(encoding="utf-8")
    init_contract = (
        "pid_owned()",
        "owned_pids()",
        "wait_owned_gone()",
        "kill -9",
        'owned_count "$DAEMON"',
        'owned_count "$WEB_MARKER"',
    )
    if any(fragment not in primary_init for fragment in init_contract):
        raise RuntimeError("package-owned primary init PID handoff contract is incomplete")
    gates["primaryServicePidHandoff"] = "PASS"

    updater_script = (system_root / "opt/libexec/broray-light-updater/broray-light-updater.sh").read_text(encoding="utf-8")
    if 'mv -fT "$temporary" "$CURRENT_PATH"' not in updater_script:
        raise RuntimeError("updater current-slot switch does not prohibit destination symlink dereference")
    if 'mv -f "$temporary" "$CURRENT_PATH"' in updater_script:
        raise RuntimeError("updater retains the BusyBox destination-symlink dereference primitive")
    gates["atomicSymlinkSwitchNoDereference"] = "PASS"

    env, tools = prepare_tools(root, args.dash.resolve(), args.jq.resolve(), args.minisign.resolve(), args.python.resolve())
    env["BRORAY_LIGHT_ROOT_PREFIX"] = posix(system_root)
    env["BRORAY_LIGHT_SKIP_SERVICE_START"] = "1"
    verify_hook = tools / "verify-xray"
    write_shim(verify_hook, "#!/bin/sh\nexit 0\n")
    env["BRORAY_LIGHT_XRAY_VERIFY_HOOK"] = posix(verify_hook)
    env["BRORAY_LIGHT_XRAY_EXECUTABLE_HOOK"] = posix(verify_hook)
    dash = str(args.dash.resolve())

    run([dash, posix(control_root / "preinst")], env=env)
    run([dash, posix(control_root / "postinst")], env=env)
    app_root = system_root / "opt/broray-light"
    runtime = app_root / "runtime/xray"
    if sha256(runtime) != XRAY_SHA256 or not (app_root / "current").exists():
        raise RuntimeError("clean install contract failed")
    gates["isolatedCleanInstall"] = "PASS"
    runtime_before = sha256(runtime)
    run([dash, posix(control_root / "postinst")], env=env)
    if sha256(runtime) != runtime_before:
        raise RuntimeError("rerun replaced verified Xray")
    gates["installerRerun"] = "PASS"
    gates["exactXrayRuntime"] = "PASS"

    conflict_root = root / "conflict-system"
    (conflict_root / "opt/broray").mkdir(parents=True)
    conflict_env = env.copy()
    conflict_env["BRORAY_LIGHT_ROOT_PREFIX"] = posix(conflict_root)
    run([dash, posix(control_root / "preinst")], env=conflict_env, expected=1)
    gates["coownershipFailClosed"] = "PASS"

    persistent = {
        app_root / "config/user.json": b'{"keep":"config"}\n',
        app_root / "servers/manual.json": b'{"keep":"server"}\n',
        app_root / "subscriptions/one.json": b'{"keep":"subscription"}\n',
    }
    for path, payload in persistent.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    clone_slot(app_root, RELEASE_ID, "0.1.0-r8")
    set_current(app_root, "0.1.0-r8")
    shutil.rmtree(app_root / "releases" / RELEASE_ID)
    (app_root / "config/version").write_text("0.1.0-r8\n", encoding="utf-8")

    with tarfile.open(app_bundle, "r:gz") as archive:
        slot_manifest = json.load(archive.extractfile("SLOT-MANIFEST.json"))  # type: ignore[arg-type]
    feed = root / "feed-good"
    feed.mkdir()
    index = signed_index(
        feed, app_bundle, int(slot_manifest["appFiles"]), int(slot_manifest["appLogicalBytes"]),
        args.minisign.resolve(), args.signing_key.resolve()
    )
    updater = system_root / "opt/libexec/broray-light-updater/broray-light-updater.sh"
    service_hook = tools / "service-hook"
    health_hook = tools / "health-hook"
    write_shim(service_hook, "#!/bin/sh\nexit 0\n")
    write_shim(health_hook, '#!/bin/sh\n[ -n "${BRORAY_TEST_FAIL_HEALTH:-}" ] && [ -e "$BRORAY_TEST_FAIL_HEALTH" ] && [ "$1" = "0.1.0-r9" ] && exit 1\nexit 0\n')
    update_env = env.copy()
    update_env.update({
        "BRORAY_LIGHT_TEST_MODE": "1",
        "BRORAY_LIGHT_RELEASE_INDEX_URL": index.resolve().as_uri(),
        "BRORAY_LIGHT_SERVICE_HOOK": posix(service_hook),
        "BRORAY_LIGHT_HEALTH_HOOK": posix(health_hook),
        "BRORAY_LIGHT_PUBLIC_KEY": posix(system_root / "opt/share/broray-light/release.pub"),
    })

    relation = run([dash, posix(updater), "relation", "0.1.0-r8", RELEASE_ID], env=update_env).stdout.strip()
    equal = run([dash, posix(updater), "relation", RELEASE_ID, RELEASE_ID], env=update_env).stdout.strip()
    older = run([dash, posix(updater), "relation", "0.1.0-r10", RELEASE_ID], env=update_env).stdout.strip()
    if (relation, equal, older) != ("newer", "equal", "older"):
        raise RuntimeError(f"release relation mismatch: {(relation, equal, older)}")
    gates["releaseIdDecision"] = "PASS"
    run([dash, "-x", posix(updater), "check"], env=update_env)
    gates["signedIndexVerification"] = "PASS"
    run([dash, posix(updater), "update"], env=update_env)
    if json.loads((app_root / "current/release.json").read_text(encoding="utf-8"))["releaseId"] != RELEASE_ID:
        raise RuntimeError("update did not activate target")
    for path, payload in persistent.items():
        if path.read_bytes() != payload:
            raise RuntimeError(f"persistent state changed: {path}")
    if sha256(runtime) != runtime_before:
        raise RuntimeError("Xray runtime changed during app-slot update")
    gates["isolatedUpdate"] = "PASS"
    gates["persistence"] = "PASS"

    run([dash, posix(updater), "update"], env=update_env)
    gates["equalVersionNoOp"] = "PASS"

    clone_slot(app_root, RELEASE_ID, "0.1.0-r10")
    set_current(app_root, "0.1.0-r10")
    run([dash, posix(updater), "update"], env=update_env, expected=20)
    if json.loads((app_root / "current/release.json").read_text(encoding="utf-8"))["releaseId"] != "0.1.0-r10":
        raise RuntimeError("downgrade refusal mutated current")
    gates["downgradeRefusal"] = "PASS"

    set_current(app_root, "0.1.0-r8")
    fail_marker = root / "force-health-failure"
    fail_marker.write_text("1\n", encoding="utf-8")
    rollback_env = update_env.copy()
    rollback_env["BRORAY_TEST_FAIL_HEALTH"] = posix(fail_marker)
    run([dash, posix(updater), "update"], env=rollback_env, expected=1)
    if json.loads((app_root / "current/release.json").read_text(encoding="utf-8"))["releaseId"] != "0.1.0-r8":
        raise RuntimeError("rollback did not restore previous-good slot")
    gates["forcedHealthRollback"] = "PASS"
    fail_marker.unlink()

    bad_hash_feed = root / "feed-bad-hash"
    bad_hash_feed.mkdir()
    bad_hash_index = signed_index(
        bad_hash_feed, app_bundle, int(slot_manifest["appFiles"]), int(slot_manifest["appLogicalBytes"]),
        args.minisign.resolve(), args.signing_key.resolve(), sha_override="0" * 64
    )
    bad_env = update_env.copy()
    bad_env["BRORAY_LIGHT_RELEASE_INDEX_URL"] = bad_hash_index.resolve().as_uri()
    run([dash, posix(updater), "update"], env=bad_env, expected=1)
    gates["failedHashVerification"] = "PASS"

    malicious = root / "malicious.tar.gz"
    malicious_bundle(malicious)
    unsafe_feed = root / "feed-unsafe"
    unsafe_feed.mkdir()
    unsafe_index = signed_index(
        unsafe_feed, malicious, int(slot_manifest["appFiles"]), int(slot_manifest["appLogicalBytes"]),
        args.minisign.resolve(), args.signing_key.resolve()
    )
    unsafe_env = update_env.copy()
    unsafe_env["BRORAY_LIGHT_RELEASE_INDEX_URL"] = unsafe_index.resolve().as_uri()
    run([dash, posix(updater), "update"], env=unsafe_env, expected=1)
    if (root / "escape").exists():
        raise RuntimeError("malicious archive escaped extraction root")
    gates["maliciousArchiveRejection"] = "PASS"

    request_lock = system_root / "opt/var/lock/broray-light-updater/request.lock"
    request_lock.mkdir(parents=True, exist_ok=True)
    (request_lock / "pid").write_text("999999\n", encoding="utf-8")
    set_current(app_root, RELEASE_ID)
    run([dash, posix(updater), "update"], env=update_env)
    if request_lock.exists():
        raise RuntimeError("stale request lock not removed")
    contention_command = f"mkdir -p '{posix(request_lock)}'; echo $$ > '{posix(request_lock / 'pid')}'; '{posix(args.dash)}' '{posix(updater)}' update"
    run([dash, "-c", contention_command], env=update_env, expected=1)
    shutil.rmtree(request_lock)
    gates["requestLockContentionAndStaleOwner"] = "PASS"

    global_lock = system_root / "opt/var/lock/broray-light/global-operation.lock"
    global_lock.mkdir(parents=True, exist_ok=True)
    (global_lock / "pid").write_text("999999\n", encoding="utf-8")
    run([dash, posix(updater), "update"], env=update_env)
    contention_command = f"mkdir -p '{posix(global_lock)}'; echo $$ > '{posix(global_lock / 'pid')}'; '{posix(args.dash)}' '{posix(updater)}' update"
    run([dash, "-c", contention_command], env=update_env, expected=1)
    if not global_lock.exists():
        raise RuntimeError("foreign global lock was removed without acquisition")
    shutil.rmtree(global_lock)
    gates["globalLockContentionAndStaleOwner"] = "PASS"

    postrm_text = (control_root / "postrm").read_text(encoding="utf-8")
    postrm_commands = "\n".join(
        line for line in postrm_text.splitlines() if line.strip() and not line.lstrip().startswith("#")
    )
    if "ndmc" in postrm_commands or "lighttpd.conf" in postrm_commands or "interface" in postrm_commands:
        raise RuntimeError("package removal script mutates foreign state")
    gates["foreignStateRemovalFailClosed"] = "PASS"

    results["status"] = "PASS"
    results["packageSha256"] = sha256(package)
    results["appArchiveSha256"] = sha256(app_bundle)
    print(json.dumps(results, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
