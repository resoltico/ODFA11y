# SPDX-License-Identifier: AGPL-3.0-only
"""Shared font resources are inspected once without skipping distinct CMap streams."""

from dataclasses import replace
lazy from pathlib import Path

import pytest
from pypdf.errors import PyPdfError
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    EncodedStreamObject,
    NameObject,
)
lazy from pypdf import PdfWriter

from odfa11y.errors import ToolFailure
from odfa11y.pdf.reading import default_limits, open_pdf
from tests.fixtures.pdf import register, set_page_content, tagged_writer


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
    _read_with_limit(path, 730)
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
    with pytest.raises((ToolFailure, PyPdfError), match=r"(limit|Limit|bytes)"):
        _read_with_limit(path, 100)
    _read_with_limit(path, 123)


def _read_with_limit(path: Path, limit: int) -> None:
    selected = replace(default_limits(), decoded_bytes=limit, invocation_bytes=limit)
    with open_pdf(path, selected):
        pass
