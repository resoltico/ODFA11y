# SPDX-License-Identifier: MPL-2.0
"""PDF consumers cannot decode filtered streams outside the bounded reader."""

import importlib
import inspect
from pathlib import Path

import pytest
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    EncodedStreamObject,
    NameObject,
    StreamObject,
)

from odfa11y.errors import ToolFailure
from odfa11y.pdf import audit_pdfua, list_fonts
from odfa11y.pdf.reading import limits
from odfa11y.pdf.reading.reader import BoundedPdf
from odfa11y.rules import registry as rules
from tests.fixtures.pdf import dictionary, register, set_page_content, tagged_writer
from tests.pdf.test_pdf_forms import add_form


def test_all_filtered_reads_are_budget_owned_and_a_bypass_is_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = tagged_writer()
    for owner, key in [(writer.root_object, "/Metadata"), (writer.pages[0], "/Contents")]:
        source = owner[key].get_object()
        assert isinstance(source, DecodedStreamObject)
        owner[NameObject(key)] = register(writer, source.flate_encode())
    path = tmp_path / "bounded.pdf"
    writer.write(path)
    decoder = EncodedStreamObject.get_data
    decoded = []
    reader_path = Path(importlib.import_module("odfa11y.pdf.reading.reader").__file__)

    def guarded(stream: EncodedStreamObject) -> bytes:
        caller = inspect.stack()[1]
        assert Path(caller.filename) == reader_path, (
            "Filtered stream decoded outside the bounded reader"
        )
        assert caller.function == "data", "Filtered stream decoded outside the bounded reader"
        decoded.append(stream)
        return decoder(stream)

    monkeypatch.setattr(EncodedStreamObject, "get_data", guarded)
    assert rules.PDF001.id not in {finding.rule_id for finding in audit_pdfua(path).findings}
    assert len(decoded) == 2

    def bypass(pdf: BoundedPdf, _report: object) -> None:
        metadata = pdf.catalog["/Metadata"].get_object()
        assert isinstance(metadata, StreamObject)
        metadata.get_data()

    monkeypatch.setattr("odfa11y.pdf.audit._audit_xmp", bypass)
    with pytest.raises(AssertionError, match="outside the bounded reader"):
        audit_pdfua(path)


def test_fonts_in_invoked_forms_are_included(tmp_path: Path) -> None:
    writer = tagged_writer()
    set_page_content(writer, writer.pages[0], "/Fm Do")
    reference = add_form(writer, "BT /FF 12 Tf (Form text) Tj ET")
    form = dictionary(reference)
    form[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({
            NameObject("/FF"): DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Courier"),
            }),
        }),
    })
    path = tmp_path / "form-font.pdf"
    writer.write(path)
    assert {font.name for font in list_fonts(path)} == {"Courier", "Helvetica"}


def test_font_inspection_cannot_skip_stream_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "font-limit.pdf"
    tagged_writer().write(path)
    monkeypatch.setattr(limits, "MAX_CONTENT_BYTES", 10)
    with pytest.raises(ToolFailure, match=r"limit|Limit"):
        list_fonts(path)
