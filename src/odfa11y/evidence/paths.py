# SPDX-License-Identifier: MPL-2.0
"""The one definition of a safe bundle-relative file name, shared by writer and verifier."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

MANIFEST_NAME = "manifest.json"
FORBIDDEN_CHARACTERS = re.compile(r'[\x00-\x1f\x7f\\\ud800-\udfff<>:"|?*]')
WINDOWS_DEVICE = re.compile(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?")
MAX_COMPONENT_BYTES = 255
RESERVED_BUNDLE_FILES = frozenset({MANIFEST_NAME, "run.json", "review.md"})


def unsafe_reason(name: str) -> str | None:
    """Explain why a name cannot be a file inside a bundle.

    A safe name is a normalised relative POSIX path that every supported filesystem can hold:
    no empty, ``.`` or ``..`` parts, no backslash, control character, unpaired surrogate or
    character Windows forbids, no component that is a Windows device name, ends in a dot or
    space, or exceeds 255 bytes, and not the root manifest's name in any letter case.

    Returns
    -------
    str | None
        The reason the name is unsafe, or None when it is safe.

    """
    checks = (
        (not name, "empty name"),
        (
            bool(FORBIDDEN_CHARACTERS.search(name)),
            "contains a backslash, control or Windows-forbidden character",
        ),
        (name.startswith("/"), "is absolute"),
        (
            any(part in {"", ".", ".."} for part in name.split("/"))
            or PurePosixPath(name).as_posix() != name,
            "is not a normalised relative path",
        ),
        (name.casefold() == MANIFEST_NAME, "is the manifest's own name"),
        (
            any(
                WINDOWS_DEVICE.fullmatch(part) or part.endswith((".", " "))
                for part in name.split("/")
            ),
            "is not portable to Windows",
        ),
        (
            any(
                len(part.encode("utf-8", "replace")) > MAX_COMPONENT_BYTES
                for part in name.split("/")
            ),
            "has a component longer than 255 bytes",
        ),
    )
    return next((reason for failed, reason in checks if failed), None)


def is_reserved_bundle_file(name: str) -> bool:
    """Tell whether a name belongs to the bundle itself rather than to an artifact.

    Returns
    -------
    bool
        True for ``manifest.json``, ``run.json`` and ``REVIEW.md`` in any letter case.

    """
    return name.casefold() in RESERVED_BUNDLE_FILES
