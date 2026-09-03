#!/usr/bin/env python3
"""Static and isolated runtime proof for the R0012 AArch64 rename helper."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import struct
import subprocess
import tempfile
from pathlib import Path


PT_LOAD = 1
PT_DYNAMIC = 2
PT_INTERP = 3
PT_GNU_STACK = 0x6474E551
PF_X = 1
PF_W = 2
SHT_RELA = 4
SHT_DYNAMIC = 6
SHT_REL = 9


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def audit_elf(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    require(len(payload) >= 64, "helper is shorter than an ELF64 header")
    require(payload[:4] == b"\x7fELF", "helper ELF magic mismatch")
    require(payload[4] == 2, "helper is not ELF64")
    require(payload[5] == 1, "helper is not little-endian")
    require(payload[6] == 1, "helper ELF version mismatch")

    header = struct.unpack_from("<HHIQQQIHHHHHH", payload, 16)
    (
        elf_type,
        machine,
        version,
        _entry,
        program_offset,
        section_offset,
        _flags,
        header_size,
        program_entry_size,
        program_count,
        section_entry_size,
        section_count,
        _section_names,
    ) = header
    require(elf_type == 2, "helper ELF type is not ET_EXEC")
    require(machine == 183, "helper ELF machine is not AArch64")
    require(version == 1 and header_size == 64, "helper ELF header is malformed")
    require(program_entry_size == 56 and program_count > 0, "program headers missing")
    require(
        program_offset + program_entry_size * program_count <= len(payload),
        "program headers extend beyond helper bytes",
    )

    load_count = 0
    stack_count = 0
    for index in range(program_count):
        offset = program_offset + index * program_entry_size
        program_type, program_flags, *_rest = struct.unpack_from(
            "<IIQQQQQQ", payload, offset
        )
        require(program_type != PT_INTERP, "PT_INTERP is forbidden")
        require(program_type != PT_DYNAMIC, "PT_DYNAMIC is forbidden")
        require(
            not (program_flags & PF_W and program_flags & PF_X),
            "writable executable segment is forbidden",
        )
        if program_type == PT_LOAD:
            load_count += 1
        if program_type == PT_GNU_STACK:
            stack_count += 1
            require(not (program_flags & PF_X), "executable GNU stack is forbidden")
    require(load_count > 0, "helper has no PT_LOAD segment")
    require(stack_count == 1, "helper must have exactly one non-executable GNU stack")

    if section_count:
        require(section_entry_size == 64, "unexpected ELF64 section header size")
        require(
            section_offset + section_entry_size * section_count <= len(payload),
            "section headers extend beyond helper bytes",
        )
        for index in range(section_count):
            offset = section_offset + index * section_entry_size
            _name, section_type, *_rest = struct.unpack_from("<IIQQQQIIQQ", payload, offset)
            require(
                section_type not in {SHT_RELA, SHT_DYNAMIC, SHT_REL},
                "dynamic or relocation section is forbidden",
            )

    mode = stat.S_IMODE(path.stat().st_mode)
    require(mode == 0o755, f"helper mode is {mode:o}, expected 755")
    return {
        "path": str(path),
        "sizeBytes": len(payload),
        "sha256": sha256_bytes(payload),
        "format": "ELF64_LE_AARCH64_ET_EXEC_STATIC_FREESTANDING",
        "programHeaders": program_count,
        "loadSegments": load_count,
        "gnuStackNonExecutable": True,
        "dynamic": False,
        "relocations": False,
        "mode": "0755",
    }


def run_helper(
    helper: Path,
    runner: Path | None,
    source_parent: Path,
    destination_parent: Path,
    arguments: list[str],
) -> int:
    source_fd = os.open(source_parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    destination_fd = os.open(
        destination_parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    )

    def retain_contract_fds() -> None:
        os.dup2(source_fd, 7, inheritable=True)
        os.dup2(destination_fd, 8, inheritable=True)

    command = ([str(runner)] if runner is not None else []) + [str(helper)] + arguments
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            close_fds=False,
            preexec_fn=retain_contract_fds,
            timeout=5,
        )
    finally:
        os.close(source_fd)
        os.close(destination_fd)
    require(completed.stdout == b"", "helper unexpectedly wrote stdout")
    require(completed.stderr == b"", "helper or runner unexpectedly wrote stderr")
    require(completed.returncode >= 0, "helper terminated by signal")
    return completed.returncode


def object_identity(path: Path) -> dict[str, object]:
    metadata = path.lstat()
    result: dict[str, object] = {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode": metadata.st_mode,
        "size": metadata.st_size,
    }
    if stat.S_ISREG(metadata.st_mode):
        result["sha256"] = sha256_bytes(path.read_bytes())
    if stat.S_ISLNK(metadata.st_mode):
        result["target"] = os.readlink(path)
    return result


def reset_directory(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def prepare_source(parent: Path) -> Path:
    source = parent / "source"
    reset_directory(source)
    source.mkdir(mode=0o700)
    (source / "marker").write_bytes(b"owned-source\n")
    return source


def prepare_collision(kind: str, parent: Path, root: Path) -> Path:
    destination = parent / "destination"
    reset_directory(destination)
    if kind == "regular-file":
        destination.write_bytes(b"foreign-file\n")
    elif kind == "directory":
        destination.mkdir(mode=0o700)
        (destination / "foreign").write_bytes(b"foreign-directory\n")
    elif kind == "symlink":
        destination.symlink_to("missing-foreign-target")
    elif kind == "symlink-to-directory":
        target = root / "foreign-target-directory"
        reset_directory(target)
        target.mkdir(mode=0o700)
        destination.symlink_to(target)
    else:
        raise RuntimeError(f"unknown collision kind: {kind}")
    return destination


def runtime_matrix(helper: Path, runner: Path | None, parent: Path) -> dict[str, object]:
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="broray-light-rename-proof.", dir=parent) as raw:
        root = Path(raw)
        source_parent = root / "source-parent"
        destination_parent = root / "destination-parent"
        source_parent.mkdir(mode=0o700)
        destination_parent.mkdir(mode=0o700)

        require(
            run_helper(helper, runner, source_parent, destination_parent, []) == 64,
            "wrong argc did not return 64",
        )
        for leaf in ["", ".", "..", "has/slash", "x" * 256]:
            require(
                run_helper(
                    helper, runner, source_parent, destination_parent, [leaf, "valid"]
                )
                == 65,
                f"invalid source leaf was accepted: {leaf!r}",
            )
            require(
                run_helper(
                    helper, runner, source_parent, destination_parent, ["valid", leaf]
                )
                == 66,
                f"invalid destination leaf was accepted: {leaf!r}",
            )

        source = prepare_source(source_parent)
        source_before = object_identity(source)
        destination = destination_parent / "destination"
        require(
            run_helper(
                helper, runner, source_parent, destination_parent, ["source", "destination"]
            )
            == 0,
            "absent-destination directory rename failed",
        )
        require(not source.exists() and not source.is_symlink(), "source remains after success")
        require(object_identity(destination) == source_before, "destination identity changed")
        reset_directory(destination)

        collisions: list[dict[str, object]] = []
        for kind in ["regular-file", "directory", "symlink", "symlink-to-directory"]:
            source = prepare_source(source_parent)
            destination = prepare_collision(kind, destination_parent, root)
            source_before = object_identity(source)
            destination_before = object_identity(destination)
            return_code = run_helper(
                helper, runner, source_parent, destination_parent, ["source", "destination"]
            )
            require(return_code == 67, f"{kind} collision returned {return_code}, expected 67")
            require(object_identity(source) == source_before, f"{kind} changed source")
            require(object_identity(destination) == destination_before, f"{kind} changed destination")
            collisions.append({"kind": kind, "exitCode": return_code, "unchanged": True})
            reset_directory(source)
            reset_directory(destination)

        return {
            "filesystemRoot": str(parent),
            "absentDestination": "PASS",
            "invalidLeafAndArgc": "PASS",
            "collisions": collisions,
            "cleanup": "PASS",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--helper", type=Path, required=True)
    parser.add_argument("--runner", type=Path)
    parser.add_argument("--runtime-root", action="append", type=Path, default=[])
    args = parser.parse_args()

    helper = args.helper.resolve(strict=True)
    runner = args.runner.resolve(strict=True) if args.runner else None
    audit = audit_elf(helper)
    runtime_roots = args.runtime_root
    matrices = [runtime_matrix(helper, runner, root) for root in runtime_roots]
    print(
        json.dumps(
            {"status": "PASS", "elf": audit, "runtimeMatrices": matrices},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
