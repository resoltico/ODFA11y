# SPDX-License-Identifier: MPL-2.0
"""Invoked Forms have independent MCIDs and actual content-presence controls."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
)

from odfa11y.pdf import audit_pdfua

from .pdf_fixtures import dictionary, marked_text, register, set_page_content, tagged_writer
from .test_pdf_marked_content import leaves

if TYPE_CHECKING:
    from pathlib import Path

    from pypdf import PdfWriter
    from pypdf.generic import IndirectObject


def add_form(writer: PdfWriter, data: str) -> IndirectObject:
    stream = DecodedStreamObject()
    stream.set_data(data.encode())
    stream.update({
        NameObject("/Subtype"): NameObject("/Form"),
        NameObject("/BBox"): ArrayObject([NumberObject(n) for n in [0, 0, 100, 100]]),
        NameObject("/Resources"): writer.pages[0]["/Resources"],
    })
    reference = register(writer, stream)
    resources = writer.pages[0].get("/Resources")
    assert isinstance(resources, DictionaryObject)
    resources[NameObject("/XObject")] = DictionaryObject({NameObject("/Fm"): reference})
    return reference


def findings(tmp_path: Path, writer: PdfWriter) -> set[str]:
    path = tmp_path / "form.pdf"
    writer.write(path)
    return {f.rule_id for f in audit_pdfua(path).findings}


@pytest.mark.parametrize("case", ["unmarked", "orphan", "owned", "dangling", "duplicate"])
def test_form_content_correspondence(tmp_path: Path, case: str) -> None:
    writer = tagged_writer(["H1", "P"])
    set_page_content(writer, writer.pages[0], marked_text(0) + " /Fm Do")
    form = add_form(writer, "BT (x) Tj ET" if case == "unmarked" else marked_text(0))
    owner = dictionary(leaves(writer)[1])
    reference = DictionaryObject({
        NameObject("/Type"): NameObject("/MCR"),
        NameObject("/MCID"): NumberObject(1 if case == "dangling" else 0),
        NameObject("/Stm"): form,
    })
    owner[NameObject("/K")] = (
        ArrayObject([reference, reference]) if case == "duplicate" else reference
    )
    if case == "orphan":
        owner[NameObject("/K")] = NumberObject(1)
    rules = findings(tmp_path, writer)
    expected = {
        "unmarked": "PDF023",
        "orphan": "PDF020",
        "dangling": "PDF021",
        "duplicate": "PDF022",
    }
    if case == "owned":
        assert not rules & {"PDF000", "PDF020", "PDF021", "PDF022", "PDF023"}
    else:
        assert expected[case] in rules


@pytest.mark.parametrize("content", ["", "/Artifact BMC 0 0 m 10 10 l S EMC", "0 0 m 10 10 l S"])
def test_form_graphics_require_actual_nonartifact_content(tmp_path: Path, content: str) -> None:
    writer = tagged_writer(["Figure"], figure_alt="A line")
    set_page_content(writer, writer.pages[0], "/Figure <</MCID 0>> BDC /Fm Do EMC")
    add_form(writer, content)
    rules = findings(tmp_path, writer)
    assert ("PDF010" in rules) == (not content or "Artifact" in content)
    assert "PDF000" not in rules


def test_form_cycles_fail_explicitly(tmp_path: Path) -> None:
    writer = tagged_writer(["H1"])
    set_page_content(writer, writer.pages[0], "/Fm Do")
    add_form(writer, "/Fm Do")
    assert "PDF000" in findings(tmp_path, writer)


def test_page_and_two_form_mcids_are_distinct(tmp_path: Path) -> None:
    writer = tagged_writer(["H1", "P", "P"])
    set_page_content(writer, writer.pages[0], marked_text(0) + " /Fm1 Do /Fm2 Do")
    first = add_form(writer, marked_text(0))
    second = add_form(writer, marked_text(0))
    resources = writer.pages[0].get("/Resources")
    assert isinstance(resources, DictionaryObject)
    resources[NameObject("/XObject")] = DictionaryObject({
        NameObject("/Fm1"): first,
        NameObject("/Fm2"): second,
    })
    for owner, stream in zip(leaves(writer)[1:], [first, second], strict=True):
        dictionary(owner)[NameObject("/K")] = DictionaryObject({
            NameObject("/Type"): NameObject("/MCR"),
            NameObject("/MCID"): NumberObject(0),
            NameObject("/Stm"): stream,
        })
    assert not findings(tmp_path, writer) & {"PDF000", "PDF020", "PDF021", "PDF022", "PDF023"}


@pytest.mark.parametrize("artifact", [False, True])
def test_nested_reused_forms_resolve_shadowed_resources(tmp_path: Path, *, artifact: bool) -> None:
    writer = tagged_writer(["Figure"], figure_alt="A line")
    inner = add_form(writer, "0 0 m 10 10 l S")
    outer = add_form(writer, "/Fm Do /Fm Do")
    dictionary(outer)[NameObject("/Resources")] = DictionaryObject({
        NameObject("/XObject"): DictionaryObject({NameObject("/Fm"): inner})
    })
    # On the page /Fm is the outer Form; in the outer Form the same name means the inner.
    marker = "/Artifact BMC" if artifact else "/Figure <</MCID 0>> BDC"
    set_page_content(writer, writer.pages[0], marker + " /Fm Do EMC")
    resources = writer.pages[0].get("/Resources")
    assert isinstance(resources, DictionaryObject)
    resources[NameObject("/XObject")] = DictionaryObject({NameObject("/Fm"): outer})
    rules = findings(tmp_path, writer)
    assert "PDF000" not in rules
    assert ("PDF010" in rules) == artifact


def test_whole_object_form_ownership_is_explicitly_incomplete(tmp_path: Path) -> None:
    writer = tagged_writer(["H1"])
    set_page_content(writer, writer.pages[0], "/Fm Do")
    form = add_form(writer, "BT (x) Tj ET")
    dictionary(form)[NameObject("/StructParent")] = NumberObject(0)
    assert "PDF000" in findings(tmp_path, writer)
