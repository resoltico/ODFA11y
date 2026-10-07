# SPDX-License-Identifier: MPL-2.0
"""Hash every file of an evidence bundle and verify the hashes later."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from .paths import MANIFEST_NAME, unsafe_reason

MANIFEST_FORMAT = 1
CHUNK_BYTES = 1 << 20
SHA256_HEX = re.compile(r"[0-9a-f]{64}")
MAX_SHOWN_NAME = 120


def sha256_file(path: Path) -> str:
    """Hash a file in chunks.

    Returns
    -------
    str
        The hexadecimal SHA-256 digest.

    """
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(directory: Path) -> None:
    """Record the SHA-256 of every file in a directory except the root manifest itself.

    Raises
    ------
    ValueError
        A name is unsafe, or an entry is a symbolic link or not a regular file.

    """
    files: dict[str, str] = {}
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory).as_posix()
        if path.is_dir() and not path.is_symlink():
            continue
        if relative == MANIFEST_NAME:
            continue
        if reason := unsafe_reason(relative) or _kind_problem(path):
            msg = f"Cannot record {relative!r} in a bundle: {reason}"
            raise ValueError(msg)
        files[relative] = sha256_file(path)
    payload = {"format": MANIFEST_FORMAT, "files": files}
    (directory / MANIFEST_NAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def check_bundle(directory: str | Path) -> list[str]:
    """Verify a bundle against its manifest without trusting either.

    Manifest names are untrusted input: each is validated, then walked component by
    component without following symbolic links, so no read can leave the bundle.

    Returns
    -------
    list[str]
        Problems found: unreadable or malformed manifest, unsafe, missing or modified
        files, and any unlisted file, link or special file. Empty when the bundle is intact.

    """
    root = Path(directory)
    try:
        recorded = _read_manifest(root)
    except (OSError, ValueError, TypeError) as exc:
        return [f"Cannot read {MANIFEST_NAME}: {exc}"]
    problems: list[str] = []
    for name, digest in sorted(recorded.items()):
        problem = _file_problem(root, name, digest)
        if problem:
            problems.append(problem)
    problems.extend(_unlisted(root, set(recorded)))
    return problems


def _shown(name: str) -> str:
    return name if len(name) <= MAX_SHOWN_NAME else f"{name[:MAX_SHOWN_NAME]}..."


def _read_manifest(root: Path) -> dict[str, str]:
    if problem := _kind_problem(root / MANIFEST_NAME):
        msg = f"{MANIFEST_NAME} {problem}"
        raise ValueError(msg)
    text = (root / MANIFEST_NAME).read_text(encoding="utf-8")
    manifest = json.loads(text, object_pairs_hook=_no_duplicates)
    if not isinstance(manifest, dict) or manifest.keys() != {"format", "files"}:
        msg = "expected exactly the keys 'format' and 'files'"
        raise TypeError(msg)
    if type(manifest["format"]) is not int or manifest["format"] != MANIFEST_FORMAT:
        msg = f"unsupported format {manifest['format']!r}"
        raise ValueError(msg)
    files = manifest["files"]
    if not isinstance(files, dict):
        msg = "'files' must be an object"
        raise TypeError(msg)
    for name, digest in files.items():
        if not isinstance(digest, str) or not SHA256_HEX.fullmatch(digest):
            msg = f"invalid digest for {_shown(name)!r}"
            raise TypeError(msg)
        if reason := unsafe_reason(name):
            msg = f"unsafe name {_shown(name)!r} {reason}"
            raise ValueError(msg)
    return dict(files)


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            msg = f"duplicate key {key!r}"
            raise ValueError(msg)
        result[key] = value
    return result


def _kind_problem(path: Path) -> str | None:
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode):
        return "is a symbolic link"
    if not stat.S_ISREG(mode):
        return "is not a regular file"
    return None


def _file_problem(root: Path, name: str, digest: str) -> str | None:
    parts = name.split("/")
    current = root
    for index, part in enumerate(parts):
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            return f"Missing: {_shown(name)}"
        except OSError as exc:
            return f"Unreadable: {_shown(name)}: {exc.strerror or type(exc).__name__}"
        if stat.S_ISLNK(mode):
            return f"Unsafe: {_shown(name)} is or passes through a symbolic link"
        wanted = stat.S_ISREG if index == len(parts) - 1 else stat.S_ISDIR
        if not wanted(mode):
            return f"Unsafe: {_shown(name)} is not a regular file"
    try:
        matches = sha256_file(current) == digest
    except OSError as exc:
        return f"Unreadable: {_shown(name)}: {exc.strerror or type(exc).__name__}"
    return None if matches else f"Modified: {_shown(name)}"


def _unlisted(root: Path, listed: set[str]) -> list[str]:
    problems: list[str] = []
    for current, directories, files in os.walk(root, followlinks=False):
        base = Path(current)
        problems.extend(
            f"Unsafe: {(base / name).relative_to(root).as_posix()} is a symbolic link"
            for name in sorted(directories)
            if (base / name).is_symlink()
        )
        for name in sorted(files):
            path = base / name
            relative = path.relative_to(root).as_posix()
            if relative == MANIFEST_NAME:
                continue
            problem = _kind_problem(path)
            if problem:
                problems.append(f"Unsafe: {relative} {problem}")
            elif relative not in listed:
                problems.append(f"Unlisted: {relative}")
    return problems
