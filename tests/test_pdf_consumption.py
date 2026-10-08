# SPDX-License-Identifier: MPL-2.0
"""Compressed consumption bounds apply independently of accessibility tagging."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject

from odfa11y import pdf_consumption
from odfa11y.errors import ToolFailedError
from odfa11y.fidelity.snapshot import read_snapshot
from odfa11y.pdf import audit_pdfua
from odfa11y.pdf_consumption import check_consumption

from .pdf_fixtures import register, tagged_writer


@pytest.mark.parametrize("tagged", [False, True])
@pytest.mark.parametrize("limit", [99, 100, 101])
def test_real_compressed_content_boundary(tmp_path: Path, limit: int, *, tagged: bool) -> None:
    writer = tagged_writer(["H1"])
    del writer.root_object["/Metadata"]
    if not tagged:
        del writer.root_object["/StructTreeRoot"]
    stream = DecodedStreamObject()
    stream.set_data(b" " * 100)
    writer.pages[0][NameObject("/Contents")] = register(writer, stream.flate_encode())
    path = tmp_path / "compressed.pdf"
    writer.write(path)
    reader = PdfReader(path)
    if limit < 100:
        with pytest.raises((ToolFailedError, PyPdfError), match=r"(limit|Limit|bytes)"):
            check_consumption(reader, limit)
    else:
        check_consumption(reader, limit)


def test_aggregate_and_auxiliary_streams(tmp_path: Path) -> None:
    writer = tagged_writer(["H1"])
    references = []
    for _ in range(3):
        stream = DecodedStreamObject()
        stream.set_data(b" " * 40)
        references.append(register(writer, stream.flate_encode()))
    writer.pages[0][NameObject("/Contents")] = ArrayObject(references[:2])
    writer.root_object[NameObject("/Metadata")] = references[2]
    path = tmp_path / "aggregate.pdf"
    writer.write(path)
    with pytest.raises((ToolFailedError, PyPdfError), match=r"(limit|Limit|bytes)"):
        check_consumption(PdfReader(path), 119)
    check_consumption(PdfReader(path), 120)


@pytest.mark.parametrize("tagged", [False, True])
def test_endpoints_refuse_resource_overflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, tagged: bool
) -> None:
    writer = tagged_writer(["H1"])
    if not tagged:
        del writer.root_object["/StructTreeRoot"]
    path = tmp_path / "limited.pdf"
    writer.write(path)
    monkeypatch.setattr(pdf_consumption, "MAX_CONTENT_BYTES", 10)
    assert "PDF000" in {f.rule_id for f in audit_pdfua(path).findings}
    with pytest.raises((ToolFailedError, PyPdfError)):
        read_snapshot(path)


def test_extraction_depth_is_a_controlled_failure(tmp_path: Path) -> None:
    writer = tagged_writer(["H1"])
    stream = DecodedStreamObject()
    stream.set_data(b"[" * 2_000 + b"]" * 2_000)
    writer.pages[0][NameObject("/Contents")] = register(writer, stream)
    path = tmp_path / "deep.pdf"
    writer.write(path)
    assert "PDF000" in {f.rule_id for f in audit_pdfua(path).findings}
    with pytest.raises(ToolFailedError, match="recursion"):
        read_snapshot(path)


def test_embedded_type1_fallback_font_counts_toward_budget(tmp_path: Path) -> None:
    writer = tagged_writer(["H1"])
    del writer.root_object["/Metadata"]
    stream = DecodedStreamObject()
    stream.set_data(b" " * 100)
    font = DictionaryObject({
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/FontDescriptor"): DictionaryObject({
            NameObject("/FontFile"): register(writer, stream.flate_encode())
        }),
    })
    resources = writer.pages[0].get("/Resources")
    assert isinstance(resources, DictionaryObject)
    resources[NameObject("/Font")] = DictionaryObject({NameObject("/F1"): font})
    path = tmp_path / "type1.pdf"
    writer.write(path)
    with pytest.raises((ToolFailedError, PyPdfError)):
        check_consumption(PdfReader(path), 99)
    check_consumption(PdfReader(path), 200)
