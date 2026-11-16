# SPDX-License-Identifier: MPL-2.0
"""Durable atomic file publication and explicit directory publication policy."""

import os
import stat
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

from odfa11y.errors import IoFailure, OutputOccupied


def staging_sibling(destination: Path) -> Path:
    return destination.with_name(f".odfa11y-output-{uuid.uuid4().hex}.tmp")


def require_file_destination(destination: Path, *, replace: bool = False) -> None:
    try:
        info = destination.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISREG(info.st_mode):
        message = f"Destination must be a regular file, never a symlink: {destination.name}"
        raise OutputOccupied(message)
    if not replace:
        message = f"Destination already exists: {destination.name}; select replacement explicitly."
        raise OutputOccupied(message)


def publish_file(
    destination: str | os.PathLike[str],
    write: Callable[[BinaryIO], object],
    *,
    replace: bool = False,
) -> Path:
    destination = Path(destination)
    temporary = staging_sibling(destination)
    try:
        require_file_destination(destination, replace=replace)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with temporary.open("x+b") as stream:
            write(stream)
            stream.flush()
            os.fsync(stream.fileno())
            original = os.fstat(stream.fileno())
        current = temporary.lstat()
        if not stat.S_ISREG(current.st_mode) or not os.path.samestat(original, current):
            message = "Publication staging identity changed during writing"
            raise OutputOccupied(message)
        require_file_destination(destination, replace=replace)
        _commit_file(temporary, destination, replace=replace)
        _sync_directory(destination.parent)
    except OSError as error:
        raise IoFailure.from_oserror(error) from error
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _commit_file(temporary: Path, destination: Path, *, replace: bool) -> None:
    if replace:
        temporary.replace(destination)
        return
    # os.replace would clobber a destination created after the absence check. Link the
    # completed sibling atomically instead; the kernel enforces exclusive creation.
    try:
        os.link(temporary, destination)
    except FileExistsError as error:
        message = f"Destination appeared during publication: {destination.name}"
        raise OutputOccupied(message) from error
    temporary.unlink()


def require_empty_directory(directory: Path) -> None:
    if directory.is_symlink() or (
        directory.exists() and (not directory.is_dir() or any(directory.iterdir()))
    ):
        message = f"Output directory must not exist or must be empty: {directory.name}"
        raise OutputOccupied(message)


def publish_directory(staged: Path, destination: Path) -> None:
    try:
        require_empty_directory(destination)
        _sync_directory(staged)
        if os.name == "nt" and destination.exists():
            destination.rmdir()
        staged.replace(destination)
        _sync_directory(destination.parent)
    except OSError as error:
        raise IoFailure.from_oserror(error) from error


def _sync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def require_distinct(source: Path, destination: Path) -> None:
    if source.resolve() == destination.resolve() or (
        source.exists() and destination.exists() and source.samefile(destination)
    ):
        message = f"Destination must differ from the source: {destination.name}"
        raise OutputOccupied(message)
