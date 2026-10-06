# SPDX-License-Identifier: MPL-2.0
"""Preserve ZIP metadata and validate ODF archive invariants."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


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


def validate_archive(tmp: Path, expected_mimetype: str) -> None:
    """Check a written archive's integrity and first-member mimetype invariant.

    Raises
    ------
    ValueError
        The archive is corrupt or violates the mimetype invariant.

    """
    # Validate what we wrote before replacing the destination.
    with zipfile.ZipFile(tmp, "r") as zf:
        infos = zf.infolist()
        if not infos or infos[0].filename != "mimetype":
            msg = "Generated ODT does not place mimetype first"
            raise ValueError(msg)
        if infos[0].compress_type != zipfile.ZIP_STORED:
            msg = "Generated ODT compresses the mimetype member"
            raise ValueError(msg)
        if zf.read("mimetype").decode("ascii", "strict") != expected_mimetype:
            msg = "Generated ODT has an invalid mimetype value"
            raise ValueError(msg)
        bad = zf.testzip()
        if bad is not None:
            msg = f"Generated ODT failed ZIP CRC validation: {bad}"
            raise ValueError(msg)


MAX_ARCHIVE_MEMBERS = 10_000
MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024


def check_archive_limits(infos: list[zipfile.ZipInfo]) -> None:
    """Bound member count and declared unpacked size before decompression.

    Raises
    ------
    ValueError
        The member count or declared unpacked size exceeds its limit.

    """
    if len(infos) > MAX_ARCHIVE_MEMBERS:
        msg = f"ODT exceeds the {MAX_ARCHIVE_MEMBERS}-member archive limit"
        raise ValueError(msg)
    if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
        msg = f"ODT exceeds the {MAX_UNCOMPRESSED_BYTES}-byte unpacked archive limit"
        raise ValueError(msg)
