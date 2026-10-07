# SPDX-License-Identifier: MPL-2.0
"""Publish an evidence directory atomically."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from odfa11y.errors import OutputError
from odfa11y.staging import staging_sibling

from .manifest import write_manifest
from .paths import is_reserved_bundle_file, unsafe_reason
from .review import render_review

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .redact import Redactor

TEXT_ARTIFACT_SUFFIXES = frozenset({".xml", ".json", ".md", ".txt"})


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
    directory: str | Path,
    record: dict[str, Any],
    artifacts: Mapping[str, Path],
    redactor: Redactor,
) -> None:
    """Write artifacts, run.json, REVIEW.md and manifest.json, then publish in one rename.

    ``artifacts`` maps bundle-relative names to source files. The record, the review sheet
    and every text artifact pass through ``redactor``, so no local path reaches the bundle;
    binary artifacts are copied unchanged.

    Raises
    ------
    OutputError
        An artifact name is not a safe bundle-relative name.

    """
    target = Path(directory)
    require_free_directory(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    for name in artifacts:
        if reason := unsafe_reason(name) or (
            "belongs to the bundle itself" if is_reserved_bundle_file(name) else None
        ):
            msg = f"Unsafe bundle file name {name!r}: {reason}"
            raise OutputError(msg)
    staging = staging_sibling(target)
    staging.mkdir()
    try:
        for name, source in artifacts.items():
            destination = staging / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.suffix in TEXT_ARTIFACT_SUFFIXES:
                text = source.read_text(encoding="utf-8", errors="replace")
                destination.write_text(redactor.text(text), encoding="utf-8")
            else:
                shutil.copyfile(source, destination)
        safe_record = redactor.record(record)
        (staging / "run.json").write_text(
            json.dumps(safe_record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (staging / "REVIEW.md").write_text(render_review(safe_record), encoding="utf-8")
        write_manifest(staging)
        if target.exists():
            target.rmdir()
        staging.replace(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
