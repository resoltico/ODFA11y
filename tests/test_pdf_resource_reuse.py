# SPDX-License-Identifier: MPL-2.0
"""Shared font resources are inspected once without skipping distinct CMap streams."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    EncodedStreamObject,
    NameObject,
)

from odfa11y.errors import ToolFailedError
from odfa11y.pdf_consumption import check_consumption

from .pdf_fixtures import register, set_page_content, tagged_writer

if TYPE_CHECKING:
    from pathlib import Path

    from pypdf import PdfWriter


def _resources(writer: PdfWriter, size: int) -> DictionaryObject:
    cmap = DecodedStreamObject()
    cmap.set_data(b" " * size)
    font = DictionaryObject({NameObject("/ToUnicode"): register(writer, cmap.flate_encode())})
    return DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F"): register(writer, font)})
    })


def _form(writer: PdfWriter, resources: DictionaryObject) -> DictionaryObject:
    form = DecodedStreamObject()
    form.set_data(b"")
    form[NameObject("/Subtype")] = NameObject("/Form")
    form[NameObject("/Resources")] = register(writer, resources)
    return form


def test_repeated_form_calls_do_not_revisit_shared_font_resources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = tagged_writer(["H1"])
    del writer.root_object["/Metadata"]
    resources = _resources(writer, 30)
    form = register(writer, _form(writer, resources))
    resources[NameObject("/XObject")] = DictionaryObject({NameObject("/Fm"): form})
    set_page_content(writer, writer.pages[0], "/Fm Do " * 100)
    writer.pages[0][NameObject("/Resources")] = register(writer, resources)
    path = tmp_path / "shared.pdf"
    writer.write(path)
    calls: list[EncodedStreamObject] = []
    original = EncodedStreamObject.get_data

    def decode(stream: EncodedStreamObject) -> bytes:
        calls.append(stream)
        return original(stream)

    monkeypatch.setattr(EncodedStreamObject, "get_data", decode)
    check_consumption(PdfReader(path, strict=True), 730)
    assert len(calls) == 1


def test_distinct_form_resources_still_reject_aggregate_cmap_overflow(tmp_path: Path) -> None:
    writer = tagged_writer(["H1"])
    del writer.root_object["/Metadata"]
    shared = _resources(writer, 30)
    separate = _resources(writer, 70)
    shared[NameObject("/XObject")] = DictionaryObject({
        NameObject("/Fm"): register(writer, _form(writer, shared)),
        NameObject("/Other"): register(writer, _form(writer, separate)),
    })
    set_page_content(writer, writer.pages[0], "/Fm Do /Fm Do /Other Do")
    writer.pages[0][NameObject("/Resources")] = register(writer, shared)
    path = tmp_path / "distinct.pdf"
    writer.write(path)
    with pytest.raises((ToolFailedError, PyPdfError), match=r"(limit|Limit|bytes)"):
        check_consumption(PdfReader(path, strict=True), 100)
    check_consumption(PdfReader(path, strict=True), 123)
