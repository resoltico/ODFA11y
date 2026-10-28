# SPDX-License-Identifier: MPL-2.0
"""Run the locked type checker on explicit authored paths, including hidden source."""

from __future__ import annotations

import subprocess  # noqa: S404  Run the selected local analyzer without a shell.
import sys
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

GENERATED_DIRECTORIES = {".git", ".venv", "__pycache__", ".ruff_cache"}
ROOT_BUILD_DIRECTORIES = {"build", "dist"}


def authored_paths(root: Path) -> Iterator[Path]:
    """Yield authored files, including hidden/ignored paths, outside generated resources.

    Yields
    ------
    Path
        Files in the shared policy and analyzer discovery scope.

    """
    for directory, dirs, files in root.walk():
        excluded = GENERATED_DIRECTORIES | (ROOT_BUILD_DIRECTORIES if directory == root else set())
        dirs[:] = [name for name in dirs if name not in excluded]
        yield from (directory / name for name in files)


def check_types(root: Path) -> int:
    """Run the locked type checker on explicit authored Python paths.

    Returns
    -------
    int
        The analyzer's exit status; one for invalid configuration, empty discovery
        or unavailable execution.

    """
    try:
        tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except OSError, tomllib.TOMLDecodeError:
        sys.stderr.write("Cannot read authoritative analyzer configuration\n")
        return 1
    files = sorted(
        path.relative_to(root).as_posix() for path in authored_paths(root) if path.suffix == ".py"
    )
    if not files:
        sys.stderr.write("No Python files were checked\n")
        return 1
    try:
        return subprocess.run(  # noqa: S603  Arguments select a local tool without a shell.
            [sys.executable, "-m", "ty", "check", "--", *files], cwd=root, shell=False, check=False
        ).returncode
    except OSError:
        sys.stderr.write("Cannot execute the type checker\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(check_types(Path(__file__).resolve().parents[1]))
