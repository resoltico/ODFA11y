# SPDX-License-Identifier: MPL-2.0
"""The one definition of a safe bundle-relative file name, shared by writer and verifier."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

MANIFEST_NAME = "manifest.json"
FORBIDDEN_CHARACTERS = re.compile(r"[\x00-\x1f\x7f\\]")
WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")


def unsafe_reason(name: str) -> str | None:
    """Explain why a name cannot be a file inside a bundle.

    A safe name is a normalised relative POSIX path with no empty, ``.`` or ``..`` parts,
    no backslash or control character, no drive letter, and not the root manifest's name.

    Returns
    -------
    str | None
        The reason the name is unsafe, or None when it is safe.

    """
    checks = (
        (not name, "empty name"),
        (bool(FORBIDDEN_CHARACTERS.search(name)), "contains a backslash or control character"),
        (name.startswith("/") or bool(WINDOWS_DRIVE.match(name)), "is absolute"),
        (
            any(part in {"", ".", ".."} for part in name.split("/"))
            or PurePosixPath(name).as_posix() != name,
            "is not a normalised relative path",
        ),
        (name == MANIFEST_NAME, "is the manifest's own name"),
    )
    return next((reason for failed, reason in checks if failed), None)
