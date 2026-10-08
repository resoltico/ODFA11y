# SPDX-License-Identifier: MPL-2.0
"""Capture bounded regular input bytes in a controlled document directory."""

from __future__ import annotations

import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.errors import PackageError

if TYPE_CHECKING:
    from collections.abc import Generator
    from typing import IO

# Physical bytes, independently of the ODF archive's declared-uncompressed budget.
MAX_SOURCE_BYTES = 256 * 1024 * 1024
COPY_CHUNK_BYTES = 64 * 1024


def _require_input(info: os.stat_result) -> None:
    if not stat.S_ISREG(info.st_mode):
        msg = "Pipeline capture requires a regular file, including an ordinary file symlink"
        raise PackageError(msg)
    if info.st_size > MAX_SOURCE_BYTES:
        msg = f"Input exceeds the {MAX_SOURCE_BYTES}-byte physical capture limit"
        raise PackageError(msg)


def _copy_bounded(descriptor: int, destination: IO[bytes]) -> None:
    remaining = MAX_SOURCE_BYTES
    while chunk := os.read(descriptor, min(COPY_CHUNK_BYTES, remaining + 1)):
        if len(chunk) > remaining:
            msg = f"Input grew beyond the {MAX_SOURCE_BYTES}-byte physical capture limit"
            raise PackageError(msg)
        destination.write(chunk)
        remaining -= len(chunk)


@contextmanager
def capture_source(source: Path, *, directory: Path | None = None) -> Generator[Path]:
    """Capture one regular input, following file aliases to their actual resource directory.

    Physical input is capped independently of the ODF parser's uncompressed budget. The
    descriptor is checked again after opening; POSIX nonblocking open prevents a replaced
    FIFO from waiting for a writer. ``directory`` selects the controlled export base for an
    already validated candidate. The staging directory must be writable. No dependencies
    are copied or fetched, and this file's lifetime is owned by the context.

    Yields
    ------
    Path
        Closed private copy, safe to reopen on Windows.

    """
    source = source.resolve(strict=True)
    _require_input(source.stat())
    captured_path: Path | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
        descriptor = os.open(source, flags)
        try:
            _require_input(os.fstat(descriptor))
            with tempfile.NamedTemporaryFile(
                prefix=".odfa11y-source-",
                suffix=source.suffix,
                dir=directory or source.parent,
                delete=False,
            ) as captured:
                captured_path = Path(captured.name)
                _copy_bounded(descriptor, captured.file)
        finally:
            os.close(descriptor)
        yield captured_path
    finally:
        if captured_path is not None:
            captured_path.unlink(missing_ok=True)
