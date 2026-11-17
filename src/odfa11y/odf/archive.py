# SPDX-License-Identifier: AGPL-3.0-only
"""Preserve ZIP metadata and validate ODF archive invariants."""

import zipfile
from pathlib import PurePosixPath, PureWindowsPath
lazy from pathlib import Path
lazy from typing import BinaryIO

from odfa11y.errors import PackageError
from odfa11y.odf import names as xml_names


def clone_zipinfo(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    """Copy ZIP member metadata so rewritten archives preserve it.

    Returns
    -------
    zipfile.ZipInfo
        A new record carrying the original member's metadata.

    """
    clone = zipfile.ZipInfo(filename=info.filename, date_time=info.date_time)
    clone.compress_type = info.compress_type
    clone.comment = info.comment
    clone.extra = info.extra
    clone.create_system = info.create_system
    clone.create_version = info.create_version
    clone.extract_version = info.extract_version
    clone.flag_bits = info.flag_bits
    clone.internal_attr = info.internal_attr
    clone.external_attr = info.external_attr
    clone.volume = info.volume
    return clone


def validate_archive(tmp: Path | BinaryIO, expected_mimetype: str | None) -> None:
    """Check a written archive's integrity and first-member mimetype invariant.

    Raises
    ------
    PackageError
        The archive is corrupt or violates the mimetype invariant.

    """
    # Validate what we wrote before replacing the destination.
    with zipfile.ZipFile(tmp, "r") as zf:
        infos = zf.infolist()
        if expected_mimetype is not None:
            if not infos or infos[0].filename != xml_names.MIMETYPE_MEMBER:
                msg = "Generated package does not place mimetype first"
                raise PackageError(msg)
            if infos[0].compress_type != zipfile.ZIP_STORED:
                msg = "Generated package compresses the mimetype member"
                raise PackageError(msg)
            if zf.read(xml_names.MIMETYPE_MEMBER).decode("ascii", "strict") != expected_mimetype:
                msg = "Generated package has an invalid mimetype value"
                raise PackageError(msg)
        bad = zf.testzip()
        if bad is not None:
            msg = f"Generated package failed ZIP CRC validation: {bad}"
            raise PackageError(msg)


MAX_ARCHIVE_MEMBERS = 10_000
MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024


def check_archive_limits(infos: list[zipfile.ZipInfo]) -> None:
    """Bound member count and declared unpacked size before decompression.

    Raises
    ------
    PackageError
        The member count or declared unpacked size exceeds its limit.

    """
    if len(infos) > MAX_ARCHIVE_MEMBERS:
        msg = f"Package exceeds the {MAX_ARCHIVE_MEMBERS}-member archive limit"
        raise PackageError(msg)
    if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
        msg = f"Package exceeds the {MAX_UNCOMPRESSED_BYTES}-byte unpacked archive limit"
        raise PackageError(msg)


def is_unsafe_member_name(name: str) -> bool:
    """Whether a ZIP member name is absolute, drive-qualified or climbs out of its directory.

    Returns
    -------
    bool
        True when extracting the name could leave the target directory.

    """
    posix = PurePosixPath(name)
    windows = PureWindowsPath(name)
    return (
        posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or ".." in posix.parts
        or ".." in windows.parts
    )
