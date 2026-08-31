#!/usr/bin/env python3
"""Deterministic R0009 BROray-Light internal candidate builder."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import stat
import subprocess
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

SOURCE_COMMIT = "684b27bdb53e545047419baa87c63dd86dffa469"
SOURCE_FILES = 121
SOURCE_BYTES = 627326
SOURCE_SUMS_SHA256 = "e056585d6a517ddbbbaebf08b68f17eb2d9d7ccd68d86df5cdee9fd4665f2419"
UPDATER_ARCHIVE_SHA256 = "eaf2eafb62d1b108fe576d1fda09ae7a5d15ad90f71272abc23f321d397611b0"
UPDATER_MINISIGN_SHA256 = "cec9f88be8c975af76854a53b4d49c3d257feae38d916edb0d16fb55aacd3000"
XRAY_VERSION = "26.7.28"
XRAY_ARCHIVE_SIZE = 19699639
XRAY_ARCHIVE_SHA256 = "f5698bb218ada3b4022db26fafc39601c5f53b46b19eb76c9616325985807501"
XRAY_DIGEST_SHA256 = "7380220ffee3878f5841c5ac31e1bd2b4625d22cacc2d1248ea3dedaa255d02f"
XRAY_BINARY_SIZE = 35389566
XRAY_BINARY_SHA256 = "4b8af237444801bf17b3dc10a1c5c24581fbe3d433eba3d78c6c3a0da1df56fc"
RELEASE_ID = "0.1.0-r9"
CANDIDATE_ID = "0.1.0-r0009c04"
PACKAGE_VERSION = "0.1.0-r0009c04"
ARCHITECTURE = "aarch64-3.10"
MTIME = 0


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def gzip_deterministic(payload: bytes) -> bytes:
    return gzip.compress(payload, compresslevel=9, mtime=MTIME)


def safe_archive_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and "\\" not in name


def verify_source(repo: Path) -> dict[str, object]:
    source = repo / "src"
    files = sorted(path for path in source.rglob("*") if path.is_file())
    logical_bytes = sum(path.stat().st_size for path in files)
    if len(files) != SOURCE_FILES or logical_bytes != SOURCE_BYTES:
        raise RuntimeError(f"canonical source identity mismatch: files={len(files)} bytes={logical_bytes}")
    if sha256_file(source / "SHA256SUMS") != SOURCE_SUMS_SHA256:
        raise RuntimeError("canonical src/SHA256SUMS identity mismatch")
    for line in (source / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if sha256_file(source / relative) != expected:
            raise RuntimeError(f"canonical source member mismatch: {relative}")
    result = subprocess.run(
        ["git", "diff", "--quiet", SOURCE_COMMIT, "--", "src"], cwd=repo, check=False
    )
    if result.returncode != 0:
        raise RuntimeError("working src differs from canonical R0008 commit")
    return {"commit": SOURCE_COMMIT, "files": len(files), "logicalBytes": logical_bytes}


def git_modes(repo: Path) -> dict[str, int]:
    output = subprocess.check_output(
        ["git", "ls-tree", "-r", SOURCE_COMMIT, "src/app", "src/init"], cwd=repo, text=True
    )
    modes: dict[str, int] = {}
    for line in output.splitlines():
        metadata, name = line.split("\t", 1)
        git_mode = metadata.split(" ", 1)[0]
        modes[name.removeprefix("src/")] = 0o755 if git_mode == "100755" else 0o644
    return modes


def tar_info(name: str, mode: int, size: int = 0, kind: bytes = tarfile.REGTYPE, linkname: str = "") -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.mode = mode
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = MTIME
    info.size = size
    info.type = kind
    info.linkname = linkname
    return info


class DeterministicTar:
    def __init__(self) -> None:
        self.buffer = io.BytesIO()
        self.tar = tarfile.open(fileobj=self.buffer, mode="w", format=tarfile.GNU_FORMAT)
        self.directories: set[str] = set()

    def add_parent_dirs(self, name: str) -> None:
        parts = PurePosixPath(name).parts[:-1]
        current: list[str] = []
        for part in parts:
            current.append(part)
            directory = "/".join(current)
            if directory not in self.directories:
                self.tar.addfile(tar_info(directory, 0o755, kind=tarfile.DIRTYPE))
                self.directories.add(directory)

    def add_bytes(self, name: str, payload: bytes, mode: int = 0o644) -> None:
        if not safe_archive_name(name):
            raise RuntimeError(f"unsafe generated archive name: {name}")
        self.add_parent_dirs(name)
        self.tar.addfile(tar_info(name, mode, len(payload)), io.BytesIO(payload))

    def add_symlink(self, name: str, target: str) -> None:
        self.add_parent_dirs(name)
        self.tar.addfile(tar_info(name, 0o777, kind=tarfile.SYMTYPE, linkname=target))

    def finish(self) -> bytes:
        self.tar.close()
        return self.buffer.getvalue()


def source_app_files(repo: Path, modes: dict[str, int]) -> list[tuple[str, bytes, int]]:
    app_root = repo / "src" / "app"
    result = []
    for path in sorted(p for p in app_root.rglob("*") if p.is_file()):
        relative = path.relative_to(app_root).as_posix()
        result.append((f"app/{relative}", path.read_bytes(), modes[f"app/{relative}"]))
    return result


def slot_payload(repo: Path, modes: dict[str, int]) -> tuple[list[tuple[str, bytes, int]], dict[str, object]]:
    app_files = source_app_files(repo, modes)
    app_count = len(app_files)
    app_bytes = sum(len(payload) for _, payload, _ in app_files)
    release = {
        "schemaVersion": 1,
        "product": "BROray-Light",
        "releaseId": RELEASE_ID,
        "candidateId": CANDIDATE_ID,
        "version": "0.1.0-dev",
        "architecture": ARCHITECTURE,
        "sourceCommit": SOURCE_COMMIT,
        "lifecycleContract": "light-app-symlink-switch/1",
        "protocols": ["VLESS"],
    }
    release_payload = json_bytes(release)
    sums_lines = [f"{sha256_bytes(payload)}  {name}" for name, payload, _ in app_files]
    sums_lines.append(f"{sha256_bytes(release_payload)}  release.json")
    sums_payload = ("\n".join(sums_lines) + "\n").encode("utf-8")
    manifest = {
        "schemaVersion": 1,
        "layout": "broray-light-app-slot/1",
        "product": "BROray-Light",
        "releaseId": RELEASE_ID,
        "candidateId": CANDIDATE_ID,
        "appFiles": app_count,
        "appLogicalBytes": app_bytes,
        "appSha256SumsSha256": sha256_bytes(sums_payload),
        "source": {"commit": SOURCE_COMMIT, "files": SOURCE_FILES, "logicalBytes": SOURCE_BYTES},
    }
    members = app_files + [
        ("release.json", release_payload, 0o644),
        ("APP-SHA256SUMS", sums_payload, 0o644),
        ("SLOT-MANIFEST.json", json_bytes(manifest), 0o644),
    ]
    return members, manifest


def build_app_archive(members: list[tuple[str, bytes, int]]) -> bytes:
    archive = DeterministicTar()
    for name, payload, mode in members:
        archive.add_bytes(name, payload, mode)
    return gzip_deterministic(archive.finish())


def verify_external_inputs(updater_archive: Path, xray_archive: Path, xray_digest: Path) -> tuple[bytes, bytes]:
    if sha256_file(updater_archive) != UPDATER_ARCHIVE_SHA256:
        raise RuntimeError("pinned updater-v5 archive mismatch")
    with tarfile.open(updater_archive, "r:gz") as archive:
        for member in archive.getmembers():
            if not safe_archive_name(member.name) or not (member.isfile() or member.isdir()):
                raise RuntimeError(f"unsafe pinned updater member: {member.name}")
        extracted = archive.extractfile("opt/libexec/broray-updater/minisign")
        if extracted is None:
            raise RuntimeError("pinned updater minisign missing")
        minisign = extracted.read()
    if sha256_bytes(minisign) != UPDATER_MINISIGN_SHA256:
        raise RuntimeError("pinned updater minisign mismatch")
    if xray_archive.stat().st_size != XRAY_ARCHIVE_SIZE or sha256_file(xray_archive) != XRAY_ARCHIVE_SHA256:
        raise RuntimeError("official Xray archive identity mismatch")
    if sha256_file(xray_digest) != XRAY_DIGEST_SHA256:
        raise RuntimeError("official Xray digest object identity mismatch")
    digest_lines = xray_digest.read_text(encoding="utf-8").replace("\r", "").splitlines()
    official = [line.split()[-1] for line in digest_lines if line.lower().startswith("sha2-256")]
    if official != [XRAY_ARCHIVE_SHA256]:
        raise RuntimeError("official Xray digest content mismatch")
    with zipfile.ZipFile(xray_archive) as archive:
        names = archive.namelist()
        if "xray" not in names or any(not safe_archive_name(name) for name in names):
            raise RuntimeError("official Xray archive layout mismatch")
        xray = archive.read("xray")
    if len(xray) != XRAY_BINARY_SIZE or sha256_bytes(xray) != XRAY_BINARY_SHA256:
        raise RuntimeError("official Xray binary identity mismatch")
    return minisign, xray


def render(path: Path, replacements: dict[str, str]) -> bytes:
    text = path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        text = text.replace(f"@{key}@", value)
    if "@" in "".join(part for part in text.split() if part.startswith("@")):
        raise RuntimeError(f"unresolved template token in {path}")
    return text.encode("utf-8")


def updater_members(repo: Path, minisign: bytes) -> list[tuple[str, bytes, int]]:
    root = repo / "updater"
    members: list[tuple[str, bytes, int]] = []
    for path in sorted(p for p in (root / "opt").rglob("*") if p.is_file()):
        relative = path.relative_to(root).as_posix()
        members.append((relative, path.read_bytes(), 0o755))
    members.append(("opt/libexec/broray-light-updater/minisign", minisign, 0o755))
    members.append(("opt/share/broray-light/release.pub", (root / "release.pub").read_bytes(), 0o644))
    sums = "\n".join(f"{sha256_bytes(payload)}  {name}" for name, payload, _ in members) + "\n"
    members.append(("SHA256SUMS", sums.encode("utf-8"), 0o644))
    return members


def build_updater_archive(members: list[tuple[str, bytes, int]]) -> bytes:
    archive = DeterministicTar()
    for name, payload, mode in members:
        archive.add_bytes(name, payload, mode)
    return gzip_deterministic(archive.finish())


def build_data_tar(
    repo: Path,
    modes: dict[str, int],
    slot_members: list[tuple[str, bytes, int]],
    updater: list[tuple[str, bytes, int]],
    xray: bytes,
) -> bytes:
    archive = DeterministicTar()
    slot_prefix = f"opt/broray-light/releases/{RELEASE_ID}"
    for name, payload, mode in slot_members:
        archive.add_bytes(f"{slot_prefix}/{name}", payload, mode)
    init_payload = (repo / "packaging/opkg/S24broray-light").read_bytes()
    archive.add_bytes("opt/etc/init.d/S24broray-light", init_payload, 0o755)
    for name, payload, mode in updater:
        if name == "SHA256SUMS":
            continue
        archive.add_bytes(name, payload, mode)
    archive.add_bytes(f"opt/libexec/broray-light-bootstrap/xray-{XRAY_VERSION}", xray, 0o755)
    return gzip_deterministic(archive.finish())


def build_control_tar(repo: Path) -> bytes:
    replacements = {
        "PACKAGE_VERSION": PACKAGE_VERSION,
        "RELEASE_ID": RELEASE_ID,
        "CANDIDATE_ID": CANDIDATE_ID,
        "XRAY_VERSION": XRAY_VERSION,
        "XRAY_BINARY_SHA256": XRAY_BINARY_SHA256,
    }
    archive = DeterministicTar()
    for name in ("control", "preinst", "postinst", "prerm", "postrm"):
        payload = render(repo / "packaging/opkg" / name, replacements)
        archive.add_bytes(name, payload, 0o644 if name == "control" else 0o755)
    return gzip_deterministic(archive.finish())


def build_ipk(control_tar: bytes, data_tar: bytes) -> bytes:
    archive = DeterministicTar()
    archive.tar.addfile(tar_info(".", 0o755, kind=tarfile.DIRTYPE))
    archive.directories.add(".")
    archive.add_bytes("./debian-binary", b"2.0\n")
    archive.add_bytes("./data.tar.gz", data_tar)
    archive.add_bytes("./control.tar.gz", control_tar)
    return gzip_deterministic(archive.finish())


def artifact(path: Path) -> dict[str, object]:
    return {"path": path.name, "sizeBytes": path.stat().st_size, "sha256": sha256_file(path)}


def build_signed_release_index(
    repo: Path,
    output: Path,
    app_identity: dict[str, object],
    slot_manifest: dict[str, object],
    minisign_tool: Path,
    signing_key: Path,
) -> tuple[Path, Path]:
    release_index = {
        "schemaVersion": 1,
        "product": "BROray-Light",
        "channel": "internal-r0009",
        "candidate": {
            "releaseId": RELEASE_ID,
            "candidateId": CANDIDATE_ID,
            "architecture": ARCHITECTURE,
            "bundle": {
                "filename": app_identity["path"],
                "url": f"https://internal.invalid/broray-light/R0009/{app_identity['path']}",
                "sizeBytes": app_identity["sizeBytes"],
                "sha256": app_identity["sha256"],
            },
            "appSlot": {
                "fileCount": slot_manifest["appFiles"],
                "logicalBytes": slot_manifest["appLogicalBytes"],
            },
        },
    }
    release_path = output / "release.json"
    signature_path = output / "release.json.minisig"
    release_path.write_bytes(json_bytes(release_index))
    subprocess.run(
        [
            str(minisign_tool),
            "-S",
            "-W",
            "-s",
            str(signing_key),
            "-m",
            str(release_path),
            "-x",
            str(signature_path),
            "-c",
            "BROray-Light R0009 internal",
            "-t",
            f"releaseId={RELEASE_ID}",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            str(minisign_tool),
            "-V",
            "-p",
            str(repo / "updater" / "release.pub"),
            "-m",
            str(release_path),
            "-x",
            str(signature_path),
        ],
        check=True,
        capture_output=True,
    )
    return release_path, signature_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--updater-platform", type=Path, required=True)
    parser.add_argument("--xray-archive", type=Path, required=True)
    parser.add_argument("--xray-digest", type=Path, required=True)
    parser.add_argument("--minisign-tool", type=Path, required=True)
    parser.add_argument("--signing-key", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    source_identity = verify_source(repo)
    modes = git_modes(repo)
    minisign, xray = verify_external_inputs(args.updater_platform, args.xray_archive, args.xray_digest)
    slot_members, slot_manifest = slot_payload(repo, modes)
    app_payload = build_app_archive(slot_members)
    updater_source_members = updater_members(repo, minisign)
    updater_payload = build_updater_archive(updater_source_members)
    data_tar = build_data_tar(repo, modes, slot_members, updater_source_members, xray)
    control_tar = build_control_tar(repo)
    ipk_payload = build_ipk(control_tar, data_tar)

    app_path = output / f"broray-light-app-{CANDIDATE_ID}.tar.gz"
    updater_path = output / "broray-light-updater-platform-5-light1.tar.gz"
    package_name = f"broray-light_{PACKAGE_VERSION}_{ARCHITECTURE}.ipk"
    package_path = output / package_name
    app_path.write_bytes(app_payload)
    updater_path.write_bytes(updater_payload)
    package_path.write_bytes(ipk_payload)

    package_identity = artifact(package_path)
    installer_replacements = {
        "PACKAGE_URL": f"https://internal.invalid/broray-light/R0009/{package_name}",
        "PACKAGE_SIZE": str(package_identity["sizeBytes"]),
        "PACKAGE_SHA256": str(package_identity["sha256"]),
        "PACKAGE_NAME": package_name,
    }
    installer_path = output / f"broray-light-install-{CANDIDATE_ID}.sh"
    installer_path.write_bytes(render(repo / "packaging/installer/broray-light-install.sh.in", installer_replacements))
    os.chmod(installer_path, 0o755)

    app_identity = artifact(app_path)
    release_path, signature_path = build_signed_release_index(
        repo, output, app_identity, slot_manifest, args.minisign_tool.resolve(), args.signing_key.resolve()
    )
    artifacts = [
        artifact(path)
        for path in (app_path, updater_path, package_path, installer_path, release_path, signature_path)
    ]
    manifest = {
        "schemaVersion": 1,
        "stage": "R0009",
        "product": "BROray-Light",
        "releaseId": RELEASE_ID,
        "candidateId": CANDIDATE_ID,
        "candidateReady": False,
        "publication": "INTERNAL_NOT_PUBLISHED",
        "signedReleaseIndex": {
            "index": release_path.name,
            "signature": signature_path.name,
            "publicKey": "updater/release.pub",
        },
        "source": source_identity,
        "slot": slot_manifest,
        "updater": {"engine": "broray-light-updater/5-light1", "service": "S23broray-light-updater"},
        "xray": {
            "version": XRAY_VERSION,
            "architecture": ARCHITECTURE,
            "binarySizeBytes": XRAY_BINARY_SIZE,
            "binarySha256": XRAY_BINARY_SHA256,
            "installPath": "/opt/broray-light/runtime/xray",
        },
        "artifacts": artifacts,
    }
    manifest_path = output / "CANDIDATE-MANIFEST.json"
    manifest_path.write_bytes(json_bytes(manifest))
    artifacts.append(artifact(manifest_path))
    sums_path = output / "SHA256SUMS"
    sums_path.write_text("\n".join(f"{entry['sha256']}  {entry['path']}" for entry in artifacts) + "\n", encoding="utf-8", newline="\n")
    summary = {"status": "PASS", "output": str(output), "artifacts": artifacts + [artifact(sums_path)]}
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
