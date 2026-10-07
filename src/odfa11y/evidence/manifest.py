# SPDX-License-Identifier: MPL-2.0
"""Hash every file of an evidence bundle and verify the hashes later."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

MANIFEST_NAME = "manifest.json"
MANIFEST_FORMAT = 1
CHUNK_BYTES = 1 << 20


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
    """Record the SHA-256 of every file in a directory except the manifest itself."""
    files = {
        path.relative_to(directory).as_posix(): sha256_file(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name != MANIFEST_NAME
    }
    payload = {"format": MANIFEST_FORMAT, "files": files}
    (directory / MANIFEST_NAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def check_bundle(directory: str | Path) -> list[str]:
    """Verify a bundle against its manifest.

    Returns
    -------
    list[str]
        Problems found: unreadable manifest, missing, modified or unlisted files. Empty when
        the bundle is intact.

    """
    root = Path(directory)
    try:
        manifest = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
        recorded: dict[str, str] = dict(manifest["files"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"Cannot read {MANIFEST_NAME}: {exc}"]
    problems = []
    for name, digest in sorted(recorded.items()):
        path = root / name
        if not path.is_file():
            problems.append(f"Missing: {name}")
        elif sha256_file(path) != digest:
            problems.append(f"Modified: {name}")
    listed = set(recorded)
    problems.extend(
        f"Unlisted: {path.relative_to(root).as_posix()}"
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and path.name != MANIFEST_NAME
        and path.relative_to(root).as_posix() not in listed
    )
    return problems
