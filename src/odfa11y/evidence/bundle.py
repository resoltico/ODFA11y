# SPDX-License-Identifier: MPL-2.0
"""Publish an evidence directory atomically."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from odfa11y.errors import OutputError

from .manifest import write_manifest
from .review import render_review

if TYPE_CHECKING:
    from collections.abc import Mapping


def require_free_directory(directory: Path) -> None:
    """Ensure a bundle directory does not exist or is empty.

    Raises
    ------
    OutputError
        The path exists and is not an empty directory.

    """
    if directory.exists() and not (directory.is_dir() and not any(directory.iterdir())):
        msg = f"Evidence directory must not exist or must be empty: {directory}"
        raise OutputError(msg)


def write_bundle(
    directory: str | Path, record: dict[str, Any], artifacts: Mapping[str, Path]
) -> None:
    """Write artifacts, run.json, REVIEW.md and manifest.json, then publish in one rename.

    ``artifacts`` maps bundle-relative names to source files.
    """
    target = Path(directory)
    require_free_directory(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    try:
        for name, source in artifacts.items():
            destination = staging / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        (staging / "run.json").write_text(
            json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (staging / "REVIEW.md").write_text(render_review(record), encoding="utf-8")
        write_manifest(staging)
        if target.exists():
            target.rmdir()
        staging.replace(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
