# SPDX-License-Identifier: MPL-2.0
"""Compare source archives with the authoritative contributor file inventory."""

from __future__ import annotations

import subprocess
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import tarfile
    from pathlib import Path

# Development outputs are absent in an untouched extracted archive. Exclude only the
# documented generated directories/files when tests subsequently run in that archive.
CACHE_DIRECTORIES = frozenset({"__pycache__", ".pytest_cache", ".ruff_cache", ".hypothesis"})
ROOT_GENERATED_DIRECTORIES = frozenset({".git", ".venv", "build", "dist", "htmlcov"})


def _extracted_names(root: Path) -> list[str]:
    names = []
    for directory, children, files in root.walk():
        excluded = CACHE_DIRECTORIES | (ROOT_GENERATED_DIRECTORIES if directory == root else set())
        children[:] = [name for name in children if name not in excluded]
        for name in files:
            if directory == root and (
                name in {"PKG-INFO", ".coverage"} or name.startswith(".coverage.")
            ):
                continue
            names.append((directory / name).relative_to(root).as_posix())
    return names


def source_files(root: Path) -> dict[str, bytes]:
    """Derive tracked release inputs, or contributor files in an extracted archive.

    Returns
    -------
    dict[str, bytes]
        Relative file names and exact bytes; no implicit dependency on a Git checkout.

    Raises
    ------
    ValueError
        Git inventory cannot be inspected or a tracked input is absent/unsafe.

    """
    if (root / ".git").exists():
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            check=True,
            timeout=30,
        )
        names = result.stdout.decode("utf-8").split("\0")[:-1]
    else:
        names = _extracted_names(root)
    files = {}
    for name in names:
        path = root / name
        if path.is_symlink() or not path.is_file():
            msg = f"Source inventory requires a regular file: {name}"
            raise ValueError(msg)
        files[name] = path.read_bytes()
    return files


def archive_errors(archive: tarfile.TarFile, root: Path, prefix: str) -> list[str]:
    """Require exact names/types/bytes, allowing only root PKG-INFO and directories.

    Returns
    -------
    list[str]
        Missing, altered, duplicate, unsafe or unexpected authored source inputs.

    """
    shipped: dict[str, bytes] = {}
    errors = []
    seen = set()
    for member in archive.getmembers():
        name = member.name.rstrip("/")
        parts = PurePosixPath(name).parts
        if name in seen:
            errors.append(f"Source archive duplicate member: {name}")
        seen.add(name)
        if (
            not parts
            or parts[0] != prefix
            or ".." in parts
            or "\\" in name
            or name != PurePosixPath(name).as_posix()
        ):
            errors.append(f"Source archive unsafe member: {name}")
            continue
        if member.isdir():
            continue
        if not member.isfile():
            errors.append(f"Source archive non-regular member: {name}")
            continue
        relative = name.removeprefix(prefix + "/")
        stream = archive.extractfile(member)
        if stream is not None and relative != "PKG-INFO":
            shipped[relative] = stream.read()
    expected = source_files(root)
    errors.extend(
        f"Source archive file set differs from contributor inventory: {name}"
        for name in sorted(expected.keys() ^ shipped.keys())
    )
    errors.extend(
        f"Source archive file differs from contributor inventory: {name}"
        for name in sorted(expected.keys() & shipped.keys())
        if expected[name] != shipped[name]
    )
    return errors
