# SPDX-License-Identifier: MPL-2.0
"""Verify parsed PDF diagnostics with independent synthetic PDF objects."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from odfa11y.pdfua import audit_pdfua

if TYPE_CHECKING:
    from pathlib import Path


def _writer(tag: str = "H1", *, role_map: dict[str, str] | None = None) -> PdfWriter:
    writer = PdfWriter()
    page = writer.add_blank_page(width=100, height=100)
    writer.add_metadata({"/Title": "Synthetic PDF"})
    root = writer.root_object
    root[NameObject("/Lang")] = TextStringObject("en-GB")
    root[NameObject("/MarkInfo")] = DictionaryObject({
        NameObject("/Marked"): BooleanObject(value=True)
    })
    writer.create_viewer_preferences().display_doctitle = True
    metadata = DecodedStreamObject()
    metadata.set_data(
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/" xmlns:ua="http://www.aiim.org/pdfua/ns/id/">'
        b"<ua:part>1</ua:part></x:xmpmeta>"
    )
    metadata[NameObject("/Type")] = NameObject("/Metadata")
    metadata[NameObject("/Subtype")] = NameObject("/XML")
    root[NameObject("/Metadata")] = writer._add_object(metadata)
    structure = DictionaryObject({NameObject("/Type"): NameObject("/StructTreeRoot")})
    reference = writer._add_object(structure)
    element = DictionaryObject({
        NameObject("/Type"): NameObject("/StructElem"),
        NameObject("/S"): NameObject(f"/{tag}"),
        NameObject("/P"): reference,
        NameObject("/K"): NumberObject(0),
    })
    structure[NameObject("/K")] = ArrayObject([writer._add_object(element)])
    if role_map:
        structure[NameObject("/RoleMap")] = DictionaryObject({
            NameObject(f"/{key}"): NameObject(f"/{value}") for key, value in role_map.items()
        })
    root[NameObject("/StructTreeRoot")] = reference
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})
    })
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 10 50 Td (Synthetic text) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    return writer


def test_valid_markers_and_indirect_preferences_are_detected(tmp_path: Path) -> None:
    path = tmp_path / "markers.pdf"
    writer = _writer()
    writer.write(path)
    report = audit_pdfua(path)
    assert report.error_count == 0, [issue.as_dict() for issue in report.issues]
    assert report.warning_count == 0
    assert report.metadata["pdfua_part"] == 1
    assert report.metadata["structure_tags"] == {"H1": 1}
    assert report.metadata["extractable_text_characters"] > 0


@pytest.mark.parametrize(
    "mapping", [{"Illustration": "Figure"}, {"Illustration": "Picture", "Picture": "Figure"}]
)
def test_custom_figure_roles_require_alternative_text(
    tmp_path: Path, mapping: dict[str, str]
) -> None:
    path = tmp_path / "figure.pdf"
    writer = _writer("Illustration", role_map=mapping)
    writer.write(path)
    report = audit_pdfua(path)
    assert "PDF007" in {issue.rule_id for issue in report.issues}
    assert "PDF011" not in {issue.rule_id for issue in report.issues}


@pytest.mark.parametrize("mapping", [None, {"Custom": "Other", "Other": "Custom"}])
def test_unmapped_and_cyclic_roles_are_rejected(
    tmp_path: Path, mapping: dict[str, str] | None
) -> None:
    path = tmp_path / "roles.pdf"
    _writer("Custom", role_map=mapping).write(path)
    assert "PDF011" in {issue.rule_id for issue in audit_pdfua(path).issues}


def test_false_marked_flag_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "untagged.pdf"
    writer = _writer()
    writer.root_object["/MarkInfo"][NameObject("/Marked")] = BooleanObject(value=False)
    writer.write(path)
    assert "PDF003" in {issue.rule_id for issue in audit_pdfua(path).issues}


def test_invalid_pdf_returns_error_report(tmp_path: Path) -> None:
    path = tmp_path / "invalid.pdf"
    path.write_bytes(b"not a PDF")
    assert "PDF000" in {issue.rule_id for issue in audit_pdfua(path).issues}


def test_cyclic_structure_arrays_do_not_repeat_traversal(tmp_path: Path) -> None:
    path = tmp_path / "cyclic.pdf"
    writer = _writer()
    structure = writer.root_object["/StructTreeRoot"]
    children = structure["/K"]
    reference = writer._add_object(children)
    children.append(reference)
    writer.write(path)
    report = audit_pdfua(path)
    assert report.metadata["structure_tags"] == {"H1": 1}
