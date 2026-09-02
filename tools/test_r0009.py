#!/usr/bin/env python3
"""R0009 isolated-root acceptance harness (no router or production mutation)."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

RELEASE_ID = "1.0.0-r1"
CANDIDATE_ID = "1.0.0-r1"
WEB_ASSET_CACHE_TOKEN = f"{CANDIDATE_ID}-r0010"
PREVIOUS_RELEASE_ID = "0.9.9-r99"
NEWER_RELEASE_ID = "1.0.0-r2"
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


def prepare_fake_ndmc(tools: Path, python: Path) -> Path:
    implementation = tools / "fake_ndmc.py"
    implementation.write_text(
        "import os, pathlib, sys\n"
        "state=pathlib.Path(os.environ['BRORAY_LIGHT_FAKE_NDMC_STATE']); state.mkdir(parents=True,exist_ok=True)\n"
        "args=sys.argv[1:]; cmd=args[1] if len(args)==2 and args[0]=='-c' else ''\n"
        "with (state/'commands.log').open('a',encoding='utf-8',newline='\\n') as stream: stream.write(cmd+'\\n')\n"
        "fail=os.environ.get('BRORAY_LIGHT_FAKE_NDMC_FAIL_COMMAND','')\n"
        "if fail and cmd==fail: raise SystemExit(1)\n"
        "def remove(name):\n"
        " p=state/name\n"
        " if p.exists(): p.unlink()\n"
        "if cmd=='show ndns':\n"
        " print('             name: tvervip'); print('           domain: keenetic.link'); print('          updated: yes'); print('           access: cloud'); raise SystemExit(0)\n"
        "if cmd=='show running-config':\n"
        " if (state/'proxy').exists():\n"
        "  print('ip http proxy brolight'); print('    upstream http '+(state/'host').read_text(encoding='utf-8').strip()+' 8080')\n"
        "  if (state/'domain').exists(): print('    domain ndns')\n"
        "  if (state/'ssl').exists(): print('    ssl redirect')\n"
        "  if (state/'security').exists(): print('    security-level public')\n"
        "  print('!')\n"
        " raise SystemExit(0)\n"
        "if cmd=='ip http proxy brolight': (state/'proxy').write_text('1\\n',encoding='utf-8'); raise SystemExit(0)\n"
        "if cmd.startswith('ip http proxy brolight upstream http '):\n"
        " parts=cmd.split(); (state/'host').write_text(parts[6]+'\\n',encoding='utf-8'); raise SystemExit(0)\n"
        "if cmd=='ip http proxy brolight domain ndns': (state/'domain').write_text('1\\n',encoding='utf-8'); raise SystemExit(0)\n"
        "if cmd=='ip http proxy brolight ssl redirect': (state/'ssl').write_text('1\\n',encoding='utf-8'); raise SystemExit(0)\n"
        "if cmd=='ip http proxy brolight security-level public': (state/'security').write_text('1\\n',encoding='utf-8'); raise SystemExit(0)\n"
        "if cmd=='no ip http proxy brolight':\n"
        " [remove(name) for name in ('proxy','host','domain','ssl','security')]; raise SystemExit(0)\n"
        "if cmd=='system configuration save': raise SystemExit(0)\n"
        "raise SystemExit(126)\n",
        encoding="utf-8",
        newline="\n",
    )
    wrapper = tools / "ndmc"
    write_shim(wrapper, f"#!/bin/sh\nexec '{posix(python)}' '{posix(implementation)}' \"$@\"\n")
    return wrapper


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
        "channel": "stable",
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
         "-c", "BROray-Light Stable", "-t", f"releaseId={RELEASE_ID}"],
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

    web_controller = system_root / "opt/libexec/broray-light-web-publish/broray-light-web-publish.sh"
    web_network = system_root / "opt/libexec/broray-light-web-publish/network.sh"
    web_policy = system_root / "opt/libexec/broray-light-web-publish/policy.sh"
    web_start_gate = system_root / "opt/libexec/broray-light-web-publish/start-gate.sh"
    web_ctl = system_root / "opt/bin/broray-light-web-publishctl"
    if not all(path.is_file() for path in (web_controller, web_network, web_policy, web_start_gate, web_ctl)):
        raise RuntimeError("package-owned KeenDNS WebUI publication payload is incomplete")
    web_contract = web_controller.read_text(encoding="utf-8")
    for fragment in (
        "NAME='brolight'",
        '"ip http proxy $NAME domain ndns"',
        '"ip http proxy $NAME ssl redirect"',
        '"ip http proxy $NAME security-level public"',
        "OWNERSHIP_MISMATCH",
        "transaction_fail",
        "recovery_mark",
    ):
        if fragment not in web_contract:
            raise RuntimeError(f"KeenDNS WebUI safety contract missing: {fragment}")
    gates["webPublicationPackageLayout"] = "PASS"

    manifest_path = args.build / "RELEASE-MANIFEST.json"
    if not manifest_path.is_file():
        manifest_path = args.build / "CANDIDATE-MANIFEST.json"
    candidate_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    semantic_policy_sha = "e3e0e68b10ef69fce1c504f2689d1ecbd3f8b6b78ee6e7ab03d8ea73d63607dc"
    if candidate_manifest.get("webPublication", {}).get("policySha256") != semantic_policy_sha or \
       f"BRORAY_LIGHT_WEB_POLICY_SHA256='{semantic_policy_sha}'" not in web_policy.read_text(encoding="utf-8"):
        raise RuntimeError("candidate manifest and packaged Web publication semantic policy identity differ")
    gates["webPublicationPolicyManifestIdentity"] = "PASS"

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

    retry_state = root / "web-start-retry-count"
    retry_root = root / "web-start-root"
    (retry_root / "tmp").mkdir(parents=True)
    retry_ctl = tools / "web-start-retry-ctl"
    write_shim(
        retry_ctl,
        "#!/bin/sh\n"
        "count=$(cat \"$BRORAY_LIGHT_WEB_START_TEST_STATE\" 2>/dev/null || echo 0)\n"
        "count=$((count + 1)); printf '%s\\n' \"$count\" > \"$BRORAY_LIGHT_WEB_START_TEST_STATE\"\n"
        "[ \"$count\" -ge 3 ] && exit 0\n"
        "echo 'BRORAY_LIGHT_WEB_PUBLISH_ERROR:ensure-preflight:NDNS_UNAVAILABLE:test' >&2\n"
        "exit 1\n",
    )
    retry_env = env.copy()
    retry_env.update({
        "BRORAY_ROOT": posix(retry_root),
        "BRORAY_LIGHT_WEB_START_TEST_STATE": posix(retry_state),
        "BRORAY_LIGHT_WEB_PUBLISH_RETRY_ATTEMPTS": "3",
        "BRORAY_LIGHT_WEB_PUBLISH_RETRY_DELAY_SECONDS": "0",
    })
    run([dash, "-c", f". '{posix(web_start_gate)}'; broray_light_web_publication_start_gate '{posix(retry_ctl)}'"], env=retry_env)
    if retry_state.read_text(encoding="utf-8").strip() != "3":
        raise RuntimeError("transient WebUI publication boot retry did not converge on the bounded third attempt")
    gates["webPublicationTransientBootRetry"] = "PASS"

    permanent_state = root / "web-start-permanent-count"
    permanent_ctl = tools / "web-start-permanent-ctl"
    write_shim(
        permanent_ctl,
        "#!/bin/sh\n"
        "count=$(cat \"$BRORAY_LIGHT_WEB_START_TEST_STATE\" 2>/dev/null || echo 0)\n"
        "count=$((count + 1)); printf '%s\\n' \"$count\" > \"$BRORAY_LIGHT_WEB_START_TEST_STATE\"\n"
        "echo 'BRORAY_LIGHT_WEB_PUBLISH_ERROR:ensure-preflight:OWNERSHIP_MISMATCH:test' >&2\n"
        "exit 1\n",
    )
    permanent_env = retry_env.copy()
    permanent_env["BRORAY_LIGHT_WEB_START_TEST_STATE"] = posix(permanent_state)
    run([dash, "-c", f". '{posix(web_start_gate)}'; broray_light_web_publication_start_gate '{posix(permanent_ctl)}'"], env=permanent_env, expected=1)
    if permanent_state.read_text(encoding="utf-8").strip() != "1":
        raise RuntimeError("permanent WebUI ownership failure was retried instead of failing closed")
    gates["webPublicationPermanentFailureNoRetry"] = "PASS"

    run([dash, posix(control_root / "preinst")], env=env)
    run([dash, posix(control_root / "postinst")], env=env)
    app_root = system_root / "opt/broray-light"
    session_dir = app_root / "run/web-new/sessions"
    if not session_dir.is_dir():
        raise RuntimeError("clean install did not create the private WebUI session directory")
    gates["webSessionDirectoryCleanInstall"] = "PASS"
    runtime = app_root / "runtime/xray"
    if sha256(runtime) != XRAY_SHA256 or not (app_root / "current").exists():
        raise RuntimeError("clean install contract failed")
    gates["isolatedCleanInstall"] = "PASS"

    clone_slot(app_root, RELEASE_ID, PREVIOUS_RELEASE_ID)
    set_current(app_root, PREVIOUS_RELEASE_ID)
    (app_root / "config/version").write_text(f"{PREVIOUS_RELEASE_ID}\n", encoding="utf-8")
    run([dash, posix(control_root / "postinst")], env=env)
    current_target = run([dash, posix(tools / "readlink"), (app_root / "current").as_posix()], env=env).stdout.strip()
    current_release = json.loads((app_root / "current/release.json").read_text(encoding="utf-8"))["releaseId"]
    current_version = (app_root / "config/version").read_text(encoding="utf-8").strip()
    if current_target != f"releases/{RELEASE_ID}" or current_release != RELEASE_ID or current_version != RELEASE_ID:
        raise RuntimeError("cross-release package upgrade did not activate the target slot")
    shutil.rmtree(app_root / "releases" / PREVIOUS_RELEASE_ID)
    gates["crossReleasePackageUpgradeActivatesTarget"] = "PASS"

    overlay_root = Path(__file__).resolve().parents[1] / "packaging/app-overlay"
    installed_app = app_root / "current/app"
    overlay_files = sorted(path for path in overlay_root.rglob("*") if path.is_file())
    if len(overlay_files) != 24:
        raise RuntimeError(f"unexpected corrective overlay file count: {len(overlay_files)}")
    for overlay_file in overlay_files:
        installed_file = installed_app / overlay_file.relative_to(overlay_root)
        if not installed_file.is_file() or installed_file.read_bytes() != overlay_file.read_bytes():
            raise RuntimeError(f"corrective app overlay mismatch: {overlay_file.relative_to(overlay_root)}")
    gates["correctiveOverlayExactInstall"] = "PASS"

    light_cli = (installed_app / "bin/broray").read_text(encoding="utf-8")
    if "broray_xray_command" not in light_cli or "broray_server_current" not in light_cli:
        raise RuntimeError("Light CLI does not expose the Xray and current-server commands required by Keenetic actions")
    gates["keeneticCliDispatchContract"] = "PASS"

    activation_api = (installed_app / "web-new/api/servers/activate.cgi").read_text(encoding="utf-8")
    if 'broray_server_activate "$activate_id" >/dev/null' not in activation_api or \
       'broray_server_details "$activate_id"' not in activation_api:
        raise RuntimeError("activation API does not enforce a JSON-only success response")
    gates["activationApiJsonOnly"] = "PASS"

    home_js = (installed_app / "web-new/assets/js/home.js").read_text(encoding="utf-8")
    home_html = (installed_app / "web-new/home.html").read_text(encoding="utf-8")
    if "activeServer(data.servers)" not in home_js or "server?.name" not in home_js:
        raise RuntimeError("Home does not resolve the active server name")
    if "unwrap(data.xray)" not in home_js or "api/broray/info.cgi" not in home_js:
        raise RuntimeError("Home does not normalize the Xray envelope and request Light info")
    if 'id="xrayVersion"' not in home_html or 'id="lightVersion"' not in home_html:
        raise RuntimeError("Home version presentation elements are absent")
    for functional_contract in (
        "api/servers/auto-switch-status.cgi",
        "temporaryStorage?.reinstallAllowed",
        "JSON.stringify({ mode })",
        "api/broray/update-check.cgi",
        "Проверка Stable-канала не выполнена:",
    ):
        if functional_contract not in home_js:
            raise RuntimeError(f"Home corrective functional contract is absent: {functional_contract}")
    if 'id="xrayInstallButton"' not in home_html or 'id="lightInstallButton"' not in home_html or \
       'id="failoverDetail"' not in home_html:
        raise RuntimeError("Home corrective controls are absent")
    gates["homeIdentityPresentationContract"] = "PASS"

    if "info.releaseChannel === 'stable'" not in home_js or \
       'id="keeneticCreateButton"' not in home_html or 'id="keeneticRepairButton"' not in home_html or \
       "healthy ? 'Исправно' : 'Исправить'" not in home_js:
        raise RuntimeError("Stable-channel or healthy Keenetic action-state presentation is incomplete")
    gates["stableChannelAndKeeneticActionState"] = "PASS"

    for keenetic_interface_contract in (
        'id="keeneticInterfaceName"',
        'id="keeneticState" class="interface-status-badge is-pending"',
        "facts.interfaceName || keenetic.interfaceName",
        "stateLabel = 'Активен'",
        "stateLabel = 'Не активен'",
        "stateLabel = 'Ошибка'",
        "stateLabel = 'Требует внимания'",
        "statusBadge('keeneticState', stateLabel, stateTone)",
    ):
        if keenetic_interface_contract not in home_html + home_js:
            raise RuntimeError(f"Keenetic interface name or status-card contract is absent: {keenetic_interface_contract}")
    gates["keeneticInterfaceNameAndStatusCard"] = "PASS"

    subscriptions_js = (installed_app / "web-new/assets/js/subscriptions.js").read_text(encoding="utf-8")
    subscriptions_html = (installed_app / "web-new/subscriptions.html").read_text(encoding="utf-8")
    if 'id="subName"' not in subscriptions_html or "JSON.stringify({name,url,updateImmediately:true})" not in subscriptions_js:
        raise RuntimeError("subscription custom-name contract is absent")
    if "confirm('Удалить подписку" not in subscriptions_js:
        raise RuntimeError("subscription deletion confirmation is absent")
    if "Array.isArray(data)?data:" not in subscriptions_js:
        raise RuntimeError("subscription list does not accept the backend raw-array contract")
    if "'?id=' + encodeURIComponent(subscription.id)" not in subscriptions_js:
        raise RuntimeError("subscription refresh/delete actions do not use the backend query-id contract")
    gates["subscriptionNameAndDeleteConfirmation"] = "PASS"

    if "subscription.serversCount" not in subscriptions_js or "await response.text()" not in subscriptions_js:
        raise RuntimeError("subscription count or empty-success compatibility contract is absent")
    gates["subscriptionCountAndResponseCompatibility"] = "PASS"

    subscription_details = (installed_app / "web-new/api/subscriptions/details.cgi").read_text(encoding="utf-8")
    for auto_update_contract in (
        "autoUpdatePanel(subscription)",
        "Включить автообновление",
        "Сохранить автообновление",
        "updateIntervalMinutes",
        "subscription.nextUpdateAt",
        "api/subscriptions/details.cgi?id=",
    ):
        if auto_update_contract not in subscriptions_js:
            raise RuntimeError(f"subscription auto-update UI contract is absent: {auto_update_contract}")
    if 'POST)' not in subscription_details or \
       'broray_subscription_update_settings "$subscription_id" "$settings_body"' not in subscription_details or \
       "broray_subscriptions_api_read_body_to_file" not in subscription_details:
        raise RuntimeError("subscription settings API does not expose authenticated bounded updates")
    gates["subscriptionAutoUpdateUiAndApi"] = "PASS"

    servers_js = (installed_app / "web-new/assets/js/servers.js").read_text(encoding="utf-8")
    failover_js = (installed_app / "web-new/assets/js/servers-auto-switch.js").read_text(encoding="utf-8")
    servers_common = (installed_app / "web-new/api/servers/common.sh").read_text(encoding="utf-8")
    server_check_api = (installed_app / "web-new/api/servers/check.cgi").read_text(encoding="utf-8")
    subscriptions_common = (installed_app / "web-new/api/subscriptions/common.sh").read_text(encoding="utf-8")
    for wrapper_name, wrapper in (("servers", servers_common), ("subscriptions", subscriptions_common)):
        if 'if ( "$@" ) >' not in wrapper or "|| broray_" not in wrapper or "api_payload='{}'" not in wrapper or "jq -e ." not in wrapper:
            raise RuntimeError(f"{wrapper_name} CGI response isolation and JSON normalization contract is incomplete")
    for structured_error_contract in (
        "broray_subscriptions_api_parse_error",
        "BRORAY_ERROR:*:*",
        "*[!A-Z0-9_]*",
        "ACTIVE_SERVER_CONFLICT|SERVER_SYNC_BUSY|SUBSCRIPTION_LOCKED",
        'BRORAY_SUBSCRIPTIONS_API_ERROR_STATUS="409 Conflict"',
        'BRORAY_SUBSCRIPTIONS_API_ERROR_STATUS="404 Not Found"',
        '"$BRORAY_SUBSCRIPTIONS_API_ERROR_MESSAGE"',
    ):
        if structured_error_contract not in subscriptions_common:
            raise RuntimeError(f"structured subscription error contract is absent: {structured_error_contract}")
    generic_subscription_marker = '"SUBSCRIPTION_OPERATION_FAILED"'
    generic_subscription_index = subscriptions_common.rfind(generic_subscription_marker)
    generic_subscription_window = subscriptions_common[
        generic_subscription_index:generic_subscription_index + 240
    ]
    if generic_subscription_index < 0 or \
       '"Операция с подпиской завершилась ошибкой."' not in generic_subscription_window or \
       '"$broray_subscriptions_api_message"' in generic_subscription_window:
        raise RuntimeError("subscription API does not retain a non-leaking generic fallback")
    for structured_server_error_contract in (
        "broray_servers_api_parse_error",
        'BRORAY_SERVERS_API_ERROR_CODE="ACTIVE_SERVER_CONFLICT"',
        'BRORAY_SERVERS_API_ERROR_CODE="SERVER_UNREACHABLE"',
        'BRORAY_SERVERS_API_ERROR_CODE="SERVER_CONFIG_INVALID"',
        'BRORAY_SERVERS_API_ERROR_CODE="SERVER_NOT_FOUND"',
        'BRORAY_SERVERS_API_ERROR_CODE="SERVER_DUPLICATE"',
        'BRORAY_SERVERS_API_ERROR_CODE="INVALID_VLESS"',
        'BRORAY_SERVERS_API_ERROR_STATUS="409 Conflict"',
        'BRORAY_SERVERS_API_ERROR_STATUS="422 Unprocessable Entity"',
        'BRORAY_SERVERS_API_ERROR_STATUS="404 Not Found"',
        '"$BRORAY_SERVERS_API_ERROR_MESSAGE"',
    ):
        if structured_server_error_contract not in servers_common:
            raise RuntimeError(f"structured server error contract is absent: {structured_server_error_contract}")
    generic_server_marker = '"SERVER_OPERATION_FAILED"'
    generic_server_index = servers_common.rfind(generic_server_marker)
    generic_server_window = servers_common[
        generic_server_index:generic_server_index + 220
    ]
    if generic_server_index < 0 or \
       '"Операция с сервером завершилась ошибкой."' not in generic_server_window or \
       'broray_servers_api_error_line' in generic_server_window:
        raise RuntimeError("server API does not retain a non-leaking generic fallback")
    gates["cgiResponseIsolationAndJsonNormalization"] = "PASS"

    for server_ui_contract in ("checkText(server.lastCheck)", "server-check-result", "refreshMoveButtons()", "await response.text()"):
        if server_ui_contract not in servers_js:
            raise RuntimeError(f"server result or boundary UI contract is absent: {server_ui_contract}")
    for negative_check_contract in (
        "broray_servers_api_check_completed",
        "broray_server_check",
        '"$check_server_id"',
        '>"$check_result_file" || check_rc=$?',
        '.serverId == $serverId',
        '((.success | type) == "boolean")',
        '((.checkedAt | length) > 0)',
        "[ \"$check_rc\" -ne 0 ] || check_rc=1",
    ):
        if negative_check_contract not in server_check_api:
            raise RuntimeError(f"negative server check API normalization is absent: {negative_check_contract}")
    for failover_contract in ("BROrayLightFailoverSaved", "current === window.BROrayLightFailoverSaved", "index === 0", "index === cards.length - 1"):
        if failover_contract not in failover_js:
            raise RuntimeError(f"failover reversible-dirty or boundary contract is absent: {failover_contract}")
    gates["serverResultBoundaryAndReversibleDirtyState"] = "PASS"

    xray_update_check = (installed_app / "web-new/api/xray/update-check.cgi").read_text(encoding="utf-8")
    if "broray_xray_update_check" not in xray_update_check or '"$BRORAY" xray update-check' in xray_update_check:
        raise RuntimeError("Xray update check still uses the unsupported CLI dispatch")
    if 'broray_api_success "$(cat "$output")"\n    exit 0' not in xray_update_check:
        raise RuntimeError("Xray update check success branch does not terminate before the error response")
    gates["xrayUpdateCheckBackend"] = "PASS"

    xray_update_api = (installed_app / "web-new/api/xray/update.cgi").read_text(encoding="utf-8")
    xray_web_operation = (installed_app / "lib/xray-web-operation.sh").read_text(encoding="utf-8")
    if 'update|reinstall' not in xray_web_operation or 'broray_xray_update_install "$install_mode"' not in xray_web_operation:
        raise RuntimeError("equal-version Xray reinstall is not exposed by the web operation layer")
    if 'mode="$(jq -r' not in xray_update_api or "broray_xray_web_reinstall" not in xray_update_api:
        raise RuntimeError("Xray update API does not dispatch the explicit reinstall mode")
    gates["xrayEqualVersionReinstallContract"] = "PASS"

    dedupe_cli = installed_app / "bin/broray-subscriptions"
    server_cli = installed_app / "bin/broray-servers"
    light_daemon = (installed_app / "bin/broray-lightd").read_text(encoding="utf-8")
    scheduler_cli = dedupe_cli.read_text(encoding="utf-8")
    if '"$ROOT/bin/broray-subscriptions" scheduler-once' not in light_daemon or \
       "broray_subscription_run_due" not in scheduler_cli or \
       "broray_subscription_update \"$scheduler_id\" automatic" not in scheduler_cli or \
       'broray_operation_lock_acquire "subscriptions:scheduler"' not in scheduler_cli or \
       'skipped:"operation-busy"' not in scheduler_cli or \
       '.nextUpdateEpoch // 0' not in scheduler_cli:
        raise RuntimeError("primary daemon subscription scheduler contract is incomplete")
    scheduler_root = root / "subscription-scheduler-contract"
    scheduler_lib = scheduler_root / "lib/subscription-service.sh"
    scheduler_lib.parent.mkdir(parents=True)
    write_shim(
        scheduler_lib,
        "#!/bin/sh\n"
        "BRORAY_SUB_DIR=\"$BRORAY_ROOT/config/subscriptions\"\n"
        "BRORAY_SUB_TMP=\"$BRORAY_ROOT/tmp\"\n"
        "BRORAY_SUB_LOG=\"$BRORAY_ROOT/logs/subscriptions.log\"\n"
        "broray_subscription_prepare_dirs(){ mkdir -p \"$BRORAY_SUB_DIR\" \"$BRORAY_SUB_TMP\" \"$BRORAY_ROOT/logs\"; }\n"
        "broray_subscription_now_epoch(){ printf '1000\\n'; }\n"
        "broray_subscription_validate_file(){ return 0; }\n"
        "broray_subscription_update(){ printf '%s\\n' \"$1\" >> \"$BRORAY_ROOT/scheduler-calls\"; return 0; }\n"
        "broray_subscription_summary(){ printf '{\"ok\":true}\\n'; }\n",
    )
    write_shim(
        scheduler_root / "lib/operation-lock.sh",
        "#!/bin/sh\n"
        "broray_operation_lock_acquire(){ [ \"${BRORAY_LIGHT_TEST_LOCK_BUSY:-0}\" != 1 ] || return 2; return 0; }\n"
        "broray_operation_lock_release(){ return 0; }\n",
    )
    due_dir = scheduler_root / "config/subscriptions"
    due_dir.mkdir(parents=True)
    json_write(due_dir / "due-one.json", {
        "id": "due-one", "enabled": True, "autoUpdateEnabled": True, "nextUpdateEpoch": 900,
    })
    run([dash, posix(dedupe_cli), "scheduler-once"], env={**env, "BRORAY_ROOT": posix(scheduler_root)})
    if (scheduler_root / "scheduler-calls").read_text(encoding="utf-8").splitlines() != ["due-one"]:
        raise RuntimeError("subscription scheduler did not execute the due enabled subscription exactly once")
    busy_result = run([dash, posix(dedupe_cli), "scheduler-once"], env={
        **env, "BRORAY_ROOT": posix(scheduler_root), "BRORAY_LIGHT_TEST_LOCK_BUSY": "1",
    })
    if '"skipped": "operation-busy"' not in busy_result.stdout or \
       (scheduler_root / "scheduler-calls").read_text(encoding="utf-8").splitlines() != ["due-one"]:
        raise RuntimeError("busy global operation lock did not safely skip the scheduled subscription tick")
    gates["subscriptionAutoUpdateSchedulerAndGlobalLock"] = "PASS"

    server_root = app_root / "servers"
    auto_config = app_root / "config/system/server-auto-switch.json"
    original_auto_config = auto_config.read_bytes()
    dedupe_records = {
        "manual-a": {"id": "manual-a", "identityKey": "identity-a", "source": {"type": "manual"}},
        "subscription-b": {"id": "subscription-b", "identityKey": "identity-a", "source": {"type": "subscription", "importKey": "import-x"}},
        "subscription-c": {"id": "subscription-c", "identityKey": "identity-c", "source": {"type": "subscription", "importKey": "import-y"}},
        "subscription-d": {"id": "subscription-d", "identityKey": "identity-d", "source": {"type": "subscription", "importKey": "import-y"}},
    }
    for server_id, record in dedupe_records.items():
        json_write(server_root / f"{server_id}.json", record)
    (app_root / "config/active-server").write_bytes(b"subscription-d\n")
    json_write(auto_config, {"schemaVersion": 1, "enabled": False, "failureThreshold": 3, "cooldownSeconds": 600,
                             "orderedServerIds": list(dedupe_records), "excludedServerIds": ["subscription-b"]})
    first_dedupe = json.loads(run([dash, posix(dedupe_cli), "deduplicate"], env={**env, "BRORAY_ROOT": posix(app_root)}).stdout)
    remaining = sorted(path.stem for path in server_root.glob("*.json"))
    if first_dedupe.get("removed") != 2 or remaining != ["manual-a", "subscription-d"]:
        raise RuntimeError(f"global server deduplication chose unsafe winners: {first_dedupe} {remaining}")
    deduped_config = json.loads(auto_config.read_text(encoding="utf-8"))
    if deduped_config.get("orderedServerIds") != ["manual-a", "subscription-d"] or deduped_config.get("excludedServerIds"):
        raise RuntimeError("global server deduplication left stale auto-switch references")
    second_dedupe = json.loads(run([dash, posix(dedupe_cli), "deduplicate"], env={**env, "BRORAY_ROOT": posix(app_root)}).stdout)
    if second_dedupe.get("removed") != 0:
        raise RuntimeError("global server deduplication is not idempotent")
    for path in server_root.glob("*.json"):
        path.unlink()
    (app_root / "config/active-server").unlink()
    auto_config.write_bytes(original_auto_config)
    gates["globalServerDeduplication"] = "PASS"

    delete_id = "manual-delete-reference-test"
    json_write(server_root / f"{delete_id}.json", {"schemaVersion": 2, "id": delete_id})
    json_write(auto_config, {
        "schemaVersion": 1,
        "enabled": False,
        "failureThreshold": 3,
        "cooldownSeconds": 600,
        "orderedServerIds": [delete_id, "keep-server"],
        "excludedServerIds": [delete_id],
    })
    delete_result = json.loads(run(
        [dash, posix(server_cli), "delete", delete_id],
        env={**env, "BRORAY_ROOT": posix(app_root)},
    ).stdout)
    pruned_config = json.loads(auto_config.read_text(encoding="utf-8"))
    if (server_root / f"{delete_id}.json").exists() or \
       delete_result.get("failoverReferencesPruned") is not True or \
       pruned_config.get("orderedServerIds") != ["keep-server"] or \
       pruned_config.get("excludedServerIds"):
        raise RuntimeError("server deletion left stale auto-switch references")

    rollback_id = "manual-delete-rollback-test"
    json_write(server_root / f"{rollback_id}.json", {"schemaVersion": 2, "id": rollback_id})
    auto_config.write_text("{invalid\n", encoding="utf-8", newline="\n")
    run(
        [dash, posix(server_cli), "delete", rollback_id],
        env={**env, "BRORAY_ROOT": posix(app_root)},
        expected=1,
    )
    if not (server_root / f"{rollback_id}.json").is_file():
        raise RuntimeError("server deletion did not fail closed when failover pruning preparation failed")
    (server_root / f"{rollback_id}.json").unlink()
    auto_config.write_bytes(original_auto_config)
    gates["serverDeletePrunesFailoverReferences"] = "PASS"

    theme_css = (installed_app / "web-new/assets/css/allpage.css").read_text(encoding="utf-8")
    login_html = (installed_app / "web-new/index.html").read_text(encoding="utf-8")
    if "--brand-hi" not in theme_css or ".server-card.is-active" not in theme_css or ".toast-root" not in theme_css:
        raise RuntimeError("corrective BROray-Light theme contract is incomplete")
    for spacing_contract in ("--space-section:28px", "padding:24px", "min-height:44px", "gap:20px"):
        if spacing_contract not in theme_css:
            raise RuntimeError(f"corrective spacing contract is incomplete: {spacing_contract}")
    for login_theme_contract in (
        "--panel: #14212b;",
        "width: min(478px, 100%);",
        "border-radius: 24px;",
        "font-family: Arial, sans-serif;",
        ".password-toggle",
        ".login-submit",
    ):
        if login_theme_contract not in theme_css:
            raise RuntimeError(f"BROray login theme contract is incomplete: {login_theme_contract}")
    if 'class="password-field"' not in login_html or \
       'class="password-toggle"' not in login_html or \
       'class="login-submit"' not in login_html or \
       'BROray-Light' not in login_html or 'VLESS для Keenetic' not in login_html:
        raise RuntimeError("BROray-Light login markup contract is incomplete")
    if "object-fit: cover;" not in theme_css or "border-radius: 50%;" not in theme_css or \
       ".card-label { color: var(--brand-hi); }" not in theme_css:
        raise RuntimeError("mobile circular logo or green card-label presentation contract is absent")
    gates["mobileLogoAndCardLabelColor"] = "PASS"
    for keenetic_style_contract in (
        ".keenetic-summary-row",
        ".interface-status-badge.is-active",
        ".interface-status-badge.is-inactive",
        ".interface-status-badge.is-warning",
        ".interface-status-badge.is-error",
    ):
        if keenetic_style_contract not in theme_css:
            raise RuntimeError(f"Keenetic status-card style contract is absent: {keenetic_style_contract}")
    gates["keeneticStatusCardPresentation"] = "PASS"
    if ".form-grid.failover-grid" not in theme_css or ".subscription-auto-update" not in theme_css or \
       ".subscription-auto-grid" not in theme_css:
        raise RuntimeError("failover or subscription auto-update responsive layout contract is absent")
    gates["responsiveSettingsCardLayout"] = "PASS"
    asset_version = f"?v={WEB_ASSET_CACHE_TOKEN}"
    page_version = f"?v={CANDIDATE_ID}"
    for page_name in ("index.html", "home.html", "servers.html", "subscriptions.html"):
        page_html = (installed_app / "web-new" / page_name).read_text(encoding="utf-8")
        if 'http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate"' not in page_html or \
           'http-equiv="Pragma" content="no-cache"' not in page_html:
            raise RuntimeError(f"HTML no-store fallback metadata is absent from {page_name}")
        if f"assets/css/allpage.css{asset_version}" not in page_html:
            raise RuntimeError(f"versioned CSS asset URL is absent from {page_name}")
        for asset_url in re.findall(r'(?:src|href)="(assets/(?:css|js)/[^"]+)"', page_html):
            if not asset_url.endswith(asset_version):
                raise RuntimeError(f"unversioned static asset URL in {page_name}: {asset_url}")
    gates["themePresentationContract"] = "PASS"

    for page_name in ("home.html", "servers.html", "subscriptions.html"):
        page_html = (installed_app / "web-new" / page_name).read_text(encoding="utf-8")
        for target in ("home.html", "servers.html", "subscriptions.html"):
            if f'href="{target}{page_version}"' not in page_html:
                raise RuntimeError(f"versioned HTML navigation to {target} is absent from {page_name}")
    login_js = (installed_app / "web-new/assets/js/login.js").read_text(encoding="utf-8")
    if f'const homeUrl = "/home.html{page_version}";' not in login_js:
        raise RuntimeError("login and existing-session redirects do not invalidate stale Home HTML")
    for script_name in ("home.js", "servers.js", "subscriptions.js"):
        page_js = (installed_app / "web-new/assets/js" / script_name).read_text(encoding="utf-8")
        if f"location.replace('/{page_version}')" not in page_js:
            raise RuntimeError(f"unauthorized redirect does not invalidate stale login HTML in {script_name}")
    gates["webAssetCacheToken"] = "PASS"
    cache_default = (installed_app / "share/defaults/lighttpd.conf").read_text(encoding="utf-8")
    runtime_prepare = (installed_app / "bin/broray-runtime-prepare").read_text(encoding="utf-8")
    for contract in ("mod_setenv", "setenv.add-response-header", '"Cache-Control" => "no-store, no-cache, must-revalidate"', '$HTTP["url"] =~ "(^/$|\\.html$)"'):
        if contract not in cache_default:
            raise RuntimeError(f"canonical lighttpd HTML cache contract is absent: {contract}")
    for migration_contract in ("migrate_html_cache_policy", "legacy Web publication receipt does not own the current config", "HTML-only cache policy has no ownership receipt", "ROOT_AND_HTML_RULE", ".lighttpdConfigSha256=$sha", "lighttpd -tt -f"):
        if migration_contract not in runtime_prepare:
            raise RuntimeError(f"persistent cache-policy migration contract is absent: {migration_contract}")
    gates["htmlNoStoreAndVersionedNavigation"] = "PASS"

    persistent_config = app_root / "config/lighttpd.conf"
    html_only_config = persistent_config.read_text(encoding="utf-8").replace(
        '$HTTP["url"] =~ "(^/$|\\.html$)" {',
        '$HTTP["url"] =~ "\\.html$" {',
    )
    if html_only_config == persistent_config.read_text(encoding="utf-8"):
        raise RuntimeError("could not stage the prior HTML-only cache policy")
    persistent_config.write_text(html_only_config, encoding="utf-8", newline="\n")
    migration_owner = app_root / "config/web-publish.json"
    json_write(migration_owner, {
        "schemaVersion": 1,
        "owner": "BROray-Light",
        "name": "brolight",
        "policySha256": "e3e0e68b10ef69fce1c504f2689d1ecbd3f8b6b78ee6e7ab03d8ea73d63607dc",
        "lighttpdConfigSha256": sha256(persistent_config),
    })
    migration_cli = installed_app / "bin/broray-subscriptions"
    migration_cli_original = migration_cli.read_bytes()
    try:
        write_shim(migration_cli, "#!/bin/sh\nexit 0\n")
        run([dash, posix(installed_app / "bin/broray-runtime-prepare")], env={**env, "BRORAY_ROOT": posix(app_root)})
    finally:
        migration_cli.write_bytes(migration_cli_original)
        migration_cli.chmod(0o755)
    migrated_owner = json.loads(migration_owner.read_text(encoding="utf-8"))
    if '$HTTP["url"] =~ "(^/$|\\.html$)" {' not in persistent_config.read_text(encoding="utf-8") or \
       migrated_owner.get("lighttpdConfigSha256") != sha256(persistent_config):
        raise RuntimeError("receipt-owned HTML-only cache policy did not migrate atomically to root plus HTML")
    migration_owner.unlink()
    gates["ownedHtmlOnlyCacheMigration"] = "PASS"

    runtime_before = sha256(runtime)
    run([dash, posix(control_root / "postinst")], env=env)
    if sha256(runtime) != runtime_before:
        raise RuntimeError("rerun replaced verified Xray")
    gates["installerRerun"] = "PASS"
    gates["exactXrayRuntime"] = "PASS"

    fake_ndmc = prepare_fake_ndmc(tools, args.python.resolve())
    fake_state = root / "fake-ndmc-state"
    fake_state.mkdir()
    config_check = tools / "lighttpd-config-check"
    write_shim(config_check, "#!/bin/sh\n[ -f \"$1\" ]\n")
    web_env = env.copy()
    web_env.update({
        "BRORAY_LIGHT_WEB_TEST_MODE": "1",
        "BRORAY_LIGHT_WEB_LAN_IP_OVERRIDE": "192.168.1.1",
        "BRORAY_LIGHT_WEB_NDMC": posix(fake_ndmc),
        "BRORAY_LIGHT_FAKE_NDMC_STATE": posix(fake_state),
        "BRORAY_LIGHT_WEB_CONFIG_TEST_COMMAND": posix(config_check),
        "BRORAY_LIGHT_WEB_VERIFY_DELAY_SECONDS": "0",
    })
    lighttpd_config = app_root / "config/lighttpd.conf"
    owner = app_root / "config/web-publish.json"
    baseline_config_sha = sha256(lighttpd_config)
    web_env["BRORAY_LIGHT_FAKE_NDMC_FAIL_COMMAND"] = "ip http proxy brolight ssl redirect"
    run([dash, posix(web_controller), "ensure"], env=web_env, expected=1)
    if sha256(lighttpd_config) != baseline_config_sha or owner.exists() or (fake_state / "proxy").exists():
        raise RuntimeError("failed WebUI publication did not roll back config, receipt and proxy state")
    if (app_root / "config/web-publish-recovery-required.json").exists():
        raise RuntimeError("successful publication rollback left a recovery marker")
    gates["webPublicationForcedRollback"] = "PASS"

    web_env.pop("BRORAY_LIGHT_FAKE_NDMC_FAIL_COMMAND")
    published = run([dash, posix(web_controller), "ensure"], env=web_env).stdout.strip()
    if published != "https://brolight.tvervip.keenetic.link/":
        raise RuntimeError(f"unexpected isolated KeenDNS URL: {published}")
    if 'server.bind = "192.168.1.1"' not in lighttpd_config.read_text(encoding="utf-8"):
        raise RuntimeError("successful publication did not bind Light WebUI to the exact private LAN address")
    receipt = json.loads(owner.read_text(encoding="utf-8"))
    if receipt.get("owner") != "BROray-Light" or receipt.get("publicFqdn") != "brolight.tvervip.keenetic.link":
        raise RuntimeError("WebUI publication receipt identity is invalid")
    if run([dash, posix(web_controller), "status"], env=web_env).stdout.strip() != published:
        raise RuntimeError("WebUI publication status does not reproduce the public URL")
    gates["webPublicationCleanEnsure"] = "PASS"

    publication_identity = (sha256(lighttpd_config), sha256(owner), (fake_state / "commands.log").stat().st_size)
    rerun = run([dash, posix(web_controller), "ensure"], env=web_env).stdout.strip()
    if rerun != published or sha256(lighttpd_config) != publication_identity[0] or sha256(owner) != publication_identity[1]:
        raise RuntimeError("same-state WebUI publication ensure was not deterministic")
    gates["webPublicationRerunNoOp"] = "PASS"

    (fake_state / "host").write_text("192.168.1.2\n", encoding="utf-8", newline="\n")
    before_foreign_config = sha256(lighttpd_config)
    before_foreign_owner = sha256(owner)
    run([dash, posix(web_controller), "ensure"], env=web_env, expected=1)
    if sha256(lighttpd_config) != before_foreign_config or sha256(owner) != before_foreign_owner:
        raise RuntimeError("foreign WebUI publication state was mutated")
    (fake_state / "host").write_text("192.168.1.1\n", encoding="utf-8", newline="\n")
    run([dash, posix(web_controller), "status"], env=web_env)
    gates["webPublicationForeignOwnershipFailClosed"] = "PASS"

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
    clone_slot(app_root, RELEASE_ID, PREVIOUS_RELEASE_ID)
    set_current(app_root, PREVIOUS_RELEASE_ID)
    shutil.rmtree(app_root / "releases" / RELEASE_ID)
    (app_root / "config/version").write_text(f"{PREVIOUS_RELEASE_ID}\n", encoding="utf-8")

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
    write_shim(health_hook, f'#!/bin/sh\n[ -n "${{BRORAY_TEST_FAIL_HEALTH:-}}" ] && [ -e "$BRORAY_TEST_FAIL_HEALTH" ] && [ "$1" = "{RELEASE_ID}" ] && exit 1\nexit 0\n')
    update_env = env.copy()
    update_env.update({
        "BRORAY_LIGHT_TEST_MODE": "1",
        "BRORAY_LIGHT_RELEASE_INDEX_URL": index.resolve().as_uri(),
        "BRORAY_LIGHT_SERVICE_HOOK": posix(service_hook),
        "BRORAY_LIGHT_HEALTH_HOOK": posix(health_hook),
        "BRORAY_LIGHT_PUBLIC_KEY": posix(system_root / "opt/share/broray-light/release.pub"),
    })

    relation = run([dash, posix(updater), "relation", PREVIOUS_RELEASE_ID, RELEASE_ID], env=update_env).stdout.strip()
    equal = run([dash, posix(updater), "relation", RELEASE_ID, RELEASE_ID], env=update_env).stdout.strip()
    older = run([dash, posix(updater), "relation", NEWER_RELEASE_ID, RELEASE_ID], env=update_env).stdout.strip()
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

    clone_slot(app_root, RELEASE_ID, NEWER_RELEASE_ID)
    set_current(app_root, NEWER_RELEASE_ID)
    run([dash, posix(updater), "update"], env=update_env, expected=20)
    if json.loads((app_root / "current/release.json").read_text(encoding="utf-8"))["releaseId"] != NEWER_RELEASE_ID:
        raise RuntimeError("downgrade refusal mutated current")
    gates["downgradeRefusal"] = "PASS"

    set_current(app_root, PREVIOUS_RELEASE_ID)
    fail_marker = root / "force-health-failure"
    fail_marker.write_text("1\n", encoding="utf-8")
    rollback_env = update_env.copy()
    rollback_env["BRORAY_TEST_FAIL_HEALTH"] = posix(fail_marker)
    run([dash, posix(updater), "update"], env=rollback_env, expected=1)
    if json.loads((app_root / "current/release.json").read_text(encoding="utf-8"))["releaseId"] != PREVIOUS_RELEASE_ID:
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
