# SPDX-License-Identifier: MPL-2.0
"""Locate and identify the external applications ODFA11y drives."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from odfa11y.errors import ToolNotFoundError

IDENTIFY_TIMEOUT_SECONDS = 20
VERSION_RE = re.compile(r"\d+(?:\.\d+)+")


@dataclass(frozen=True, slots=True)
class ToolIdentity:
    """Name and version of an application as it reports itself."""

    name: str
    version: str

    def as_dict(self) -> dict[str, str]:
        """Serialize the identity.

        Returns
        -------
        dict[str, str]
            The tool name and version.

        """
        return {"name": self.name, "version": self.version}


def find_executable(requested: str | Path | None, candidates: tuple[str, ...]) -> str:
    """Resolve an explicit path or program name, or search the candidate names on PATH.

    Returns
    -------
    str
        The executable's path.

    Raises
    ------
    ToolNotFoundError
        The requested executable, or every candidate, cannot be found.

    """
    if requested is not None:
        path = Path(requested)
        if path.is_file():
            if not os.access(path, os.X_OK):
                msg = f"Not executable: {requested}"
                raise ToolNotFoundError(msg)
            return str(path)
        resolved = shutil.which(str(requested))
        if resolved:
            return resolved
        msg = f"Executable not found: {requested}"
        raise ToolNotFoundError(msg)
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    msg = f"None of {', '.join(candidates)} was found on PATH."
    raise ToolNotFoundError(msg)


def identify(name: str, executable: str, version_args: tuple[str, ...]) -> ToolIdentity:
    """Ask an application for its version; failure yields ``unknown`` rather than an error.

    Returns
    -------
    ToolIdentity
        The reported version number, or ``unknown`` when it cannot be determined.

    """
    try:
        completed = subprocess.run(
            [executable, *version_args],
            capture_output=True,
            text=True,
            timeout=IDENTIFY_TIMEOUT_SECONDS,
            check=False,
        )
    except OSError, subprocess.TimeoutExpired:
        return ToolIdentity(name, "unknown")
    found = VERSION_RE.search(completed.stdout or completed.stderr)
    return ToolIdentity(name, found.group(0) if found else "unknown")
