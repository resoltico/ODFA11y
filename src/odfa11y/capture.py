# SPDX-License-Identifier: MPL-2.0
"""Capture bounded regular input bytes in a controlled document directory."""

import errno
import hashlib
import os
import stat
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
lazy from collections.abc import Generator
lazy from typing import IO

from odfa11y.errors import PackageError

# Physical bytes, independently of the ODF archive's declared-uncompressed budget.
MAX_SOURCE_BYTES = 256 * 1024 * 1024
COPY_CHUNK_BYTES = 64 * 1024


def _require_input(info: os.stat_result) -> None:
    if not stat.S_ISREG(info.st_mode):
        msg = "Source capture requires a regular file, including an ordinary file symlink"
        raise PackageError(msg)
    if info.st_size > MAX_SOURCE_BYTES:
        msg = f"Input exceeds the {MAX_SOURCE_BYTES}-byte physical capture limit"
        raise PackageError(msg)


def _copy_bounded(descriptor: int, destination: IO[bytes]) -> str:
    remaining = MAX_SOURCE_BYTES
    digest = hashlib.sha256()
    while chunk := os.read(descriptor, min(COPY_CHUNK_BYTES, remaining + 1)):
        if len(chunk) > remaining:
            msg = f"Input grew beyond the {MAX_SOURCE_BYTES}-byte physical capture limit"
            raise PackageError(msg)
        destination.write(chunk)
        digest.update(chunk)
        remaining -= len(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    name: str
    path: Path
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class CapturedSource:
    path: Path
    digest: str
    identity: SourceIdentity


@contextmanager
def capture_source(source: Path, *, directory: Path | None = None) -> Generator[CapturedSource]:
    """Acquire a bounded regular file once into a private, caller-owned lifetime.

    Resolve deliberate aliases before selection, then verify the opened descriptor's
    identity. Nonblocking, no-follow open retains FIFO and replaced-leaf protections.
    Capture never writes beside the user's source or copies its rendering dependencies.
    """
    name = source.name
    source = source.resolve(strict=True)
    selected = source.stat()
    _require_input(selected)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(source, flags)
    except OSError as error:
        if error.errno == errno.ELOOP:
            message = "Input identity changed after selection"
            raise PackageError(message) from error
        raise
    try:
        opened = os.fstat(descriptor)
        _require_input(opened)
        if not os.path.samestat(selected, opened):
            message = "Input identity changed after selection"
            raise PackageError(message)
        with tempfile.TemporaryDirectory(prefix="odfa11y-source-", dir=directory) as temporary:
            captured = Path(temporary) / source.name
            with captured.open("xb") as output:
                digest = _copy_bounded(descriptor, output)
            finished = os.fstat(descriptor)
            if (opened.st_size, opened.st_mtime_ns) != (finished.st_size, finished.st_mtime_ns):
                message = "Input changed during source capture"
                raise PackageError(message)
            os.close(descriptor)
            descriptor = None
            yield CapturedSource(
                captured,
                digest,
                SourceIdentity(name, source, opened.st_dev, opened.st_ino),
            )
    finally:
        if descriptor is not None:
            os.close(descriptor)


def source_digest(source: Path) -> str:
    """Hash regular source or evidence bytes incrementally."""
    if not source.is_file():
        message = "A digest source must be a readable regular file"
        raise PackageError(message)
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        while chunk := stream.read(COPY_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()
