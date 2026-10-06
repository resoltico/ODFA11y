# SPDX-License-Identifier: MPL-2.0
"""Reject corrupt, ambiguous and resource-exhausting ZIP inputs at their real boundary."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

import pytest

from odfa11y.audit import audit_odt
from odfa11y.odf import ODT_MIMETYPE, OdtPackage
from odfa11y.odf import archive as archive_limits

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


def test_duplicate_zip_members_are_reported_and_cannot_be_rewritten(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    content = OdtPackage(source).read("content.xml")
    with zipfile.ZipFile(source, "a") as archive, pytest.warns(UserWarning, match="Duplicate name"):
        archive.writestr("content.xml", content)
    assert "PKG006" in {issue.rule_id for issue in audit_odt(source).issues}
    destination = tmp_path / "existing.odt"
    destination.write_bytes(b"existing destination")
    with pytest.raises(ValueError, match="duplicate ZIP"):
        OdtPackage(source).save(destination)
    assert destination.read_bytes() == b"existing destination"


def test_crc_corruption_is_rejected_without_a_second_decompression_pass(tmp_path: Path) -> None:
    source = tmp_path / "corrupt.odt"
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("mimetype", ODT_MIMETYPE)
        archive.writestr("payload.bin", b"UNIQUE_CRC_SAMPLE")
    source.write_bytes(source.read_bytes().replace(b"UNIQUE_CRC_SAMPLE", b"CORRUPT_CRC_DATA_"))
    with pytest.raises(ValueError, match="CRC"):
        OdtPackage(source)


def test_member_count_limit_is_enforced_before_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    monkeypatch.setattr(archive_limits, "MAX_ARCHIVE_MEMBERS", 1)
    with pytest.raises(ValueError, match="member archive limit"):
        OdtPackage(source)


@pytest.mark.parametrize(("payload_size", "accepted"), [(25, True), (26, False)])
def test_unpacked_size_limit_accepts_boundary_and_rejects_one_extra_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload_size: int, *, accepted: bool
) -> None:
    source = tmp_path / "size.odt"
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", ODT_MIMETYPE)
        archive.writestr("payload.bin", b"x" * payload_size)
    monkeypatch.setattr(archive_limits, "MAX_UNCOMPRESSED_BYTES", 64)
    if accepted:
        assert OdtPackage(source).read("payload.bin") == b"x" * payload_size
    else:
        with pytest.raises(ValueError, match="unpacked archive limit"):
            OdtPackage(source)
