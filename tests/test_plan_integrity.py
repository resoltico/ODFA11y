# SPDX-License-Identifier: MPL-2.0
"""A plan must mean what its author reviewed: selector conflicts, fingerprints, style identity."""

from __future__ import annotations

from typing import TYPE_CHECKING, Unpack

from lxml import etree

from odfa11y.adapter import Status
from odfa11y.content import GraphicDescription, graphics_fingerprint, table_fingerprint
from odfa11y.families.text import (
    MarkTableHeaders,
    NormalizeSpacing,
    SetGraphicDescriptions,
    TableHeaders,
    derived_style_name,
)
from odfa11y.odf import OdfDocument, Part, qn, select_elements

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.adapter import Operation

    from .fixtures import Features

WRONG = "000000000000"


def open_document(tmp_path: Path, **features: Unpack[Features]) -> OdfDocument:
    """Open a synthetic document with the given features.

    Returns
    -------
    OdfDocument
        The document.

    """
    return OdfDocument.open(make_minimal_odt(tmp_path / "doc.odt", **features))


def statuses(operation: Operation, document: OdfDocument) -> tuple[Status, ...]:
    """Apply an operation and list its outcome statuses.

    Returns
    -------
    tuple[Status, ...]
        One status per outcome.

    """
    return tuple(outcome.status for outcome in operation.apply(document))


def test_conflicting_alt_text_for_one_graphic_fails_every_involved_entry(tmp_path: Path) -> None:
    document = open_document(tmp_path, with_image_without_alt=True)
    entries = {
        "Logo": GraphicDescription(description="A"),
        "logo.svg": GraphicDescription(description="B"),
    }
    outcomes = SetGraphicDescriptions(entries).apply(document)
    assert {outcome.key for outcome in outcomes} == {"Logo", "logo.svg"}
    assert all(outcome.status is Status.FAILED for outcome in outcomes)
    assert all("different description" in outcome.message for outcome in outcomes)
    assert document.edit_count == 0


def test_entries_that_set_different_fields_or_equal_values_combine(tmp_path: Path) -> None:
    document = open_document(tmp_path, with_image_without_alt=True)
    different = {
        "Logo": GraphicDescription(title="T"),
        "logo.svg": GraphicDescription(description="D"),
    }
    assert statuses(SetGraphicDescriptions(different), document) == (Status.APPLIED, Status.APPLIED)
    same = {
        "Logo": GraphicDescription(description="D"),
        "logo.svg": GraphicDescription(description="D"),
    }
    assert statuses(SetGraphicDescriptions(same), document) == (Status.UNCHANGED, Status.UNCHANGED)


def test_a_fingerprint_binds_alt_text_to_the_reviewed_graphic_and_survives_the_edit(
    tmp_path: Path,
) -> None:
    document = open_document(tmp_path, with_image_without_alt=True)
    frames = select_elements(document.tree(Part.CONTENT), "//draw:frame")
    fingerprint = graphics_fingerprint(document, frames)
    entry = {"Logo": GraphicDescription("Title", "Description", fingerprint)}
    assert statuses(SetGraphicDescriptions(entry), document) == (Status.APPLIED,)
    assert (
        graphics_fingerprint(document, frames) == fingerprint
    )  # setting alt text does not change it
    assert statuses(SetGraphicDescriptions(entry), document) == (Status.UNCHANGED,)
    stale = {"Logo": GraphicDescription("Other", fingerprint=WRONG)}
    (outcome,) = SetGraphicDescriptions(stale).apply(document)
    assert outcome.status is Status.FAILED
    assert "no longer the object" in outcome.message


def test_a_fingerprint_binds_header_rows_to_the_reviewed_table(tmp_path: Path) -> None:
    document = open_document(tmp_path, with_data_table=True)
    table = select_elements(document.tree(Part.CONTENT), "//table:table")[0]
    fingerprint = table_fingerprint(table)
    entry = {"Data": TableHeaders(1, fingerprint=fingerprint)}
    assert statuses(MarkTableHeaders(entry), document) == (Status.APPLIED,)
    assert table_fingerprint(table) == fingerprint  # moving rows into the header keeps it
    assert statuses(MarkTableHeaders(entry), document) == (Status.UNCHANGED,)


def test_a_table_that_drifted_since_review_is_refused(tmp_path: Path) -> None:
    document = open_document(tmp_path, with_data_table=True)
    table = select_elements(document.tree(Part.CONTENT), "//table:table")[0]
    fingerprint = table_fingerprint(table)
    select_elements(table, ".//text:p")[0].text = "Edited after review"
    (outcome,) = MarkTableHeaders({"Data": TableHeaders(1, fingerprint=fingerprint)}).apply(
        document
    )
    assert outcome.status is Status.FAILED
    assert "no longer the object" in outcome.message
    assert document.edit_count == 0


def test_marking_headers_keeps_a_reviewed_graphic_in_that_row_addressable(tmp_path: Path) -> None:
    document = open_document(tmp_path, with_data_table=True, with_image_without_alt=True)
    frame = select_elements(document.tree(Part.CONTENT), "//draw:frame")[0]
    cell_paragraph = select_elements(document.tree(Part.CONTENT), "//table:table-cell/text:p")[0]
    cell_paragraph.append(frame)
    fingerprint = graphics_fingerprint(document, [frame])
    graphics = SetGraphicDescriptions({
        "Logo": GraphicDescription("A logo", fingerprint=fingerprint)
    })
    assert statuses(graphics, document) == (Status.APPLIED,)
    assert statuses(MarkTableHeaders({"Data": TableHeaders(rows=1)}), document) == (Status.APPLIED,)
    assert graphics_fingerprint(document, [frame]) == fingerprint
    assert statuses(graphics, document) == (Status.UNCHANGED,)


def _spacing_document(tmp_path: Path) -> OdfDocument:
    document = open_document(tmp_path)
    paragraphs = select_elements(document.edit(Part.CONTENT), "//text:p")
    paragraphs[0].set(qn("text", "style-name"), "Body")
    paragraphs[-1].set(qn("text", "style-name"), "BodyTight")
    return OdfDocument.open(document.save(tmp_path / "prepared.odt"))


def _add_style(tree: etree._ElementTree, container: str, name: str) -> etree._Element:
    parent = select_elements(tree, f"//{container}")[0]
    style = etree.SubElement(parent, qn("style", "style"))
    style.set(qn("style", "name"), name)
    style.set(qn("style", "family"), "paragraph")
    properties = etree.SubElement(style, qn("style", "text-properties"))
    properties.set(qn("fo", "font-weight"), "bold")
    return style


def test_a_foreign_style_with_the_derived_name_is_never_overwritten(tmp_path: Path) -> None:
    document = _spacing_document(tmp_path)
    name = derived_style_name("BodyTight")
    foreign = _add_style(document.edit(Part.CONTENT), "office:automatic-styles", name)
    before = etree.tostring(foreign)
    edits = document.edit_count
    (outcome,) = NormalizeSpacing("Body paragraph.", ("BodyTight",)).apply(document)
    assert outcome.status is Status.FAILED
    assert "not an unmodified derivation" in outcome.message
    assert etree.tostring(foreign) == before
    assert document.edit_count == edits  # nothing was edited after the conflict was found


def test_a_foreign_style_in_the_styles_part_is_protected_too(tmp_path: Path) -> None:
    document = _spacing_document(tmp_path)
    name = derived_style_name("BodyTight")
    _add_style(document.edit(Part.STYLES), "office:styles", name)
    (outcome,) = NormalizeSpacing("Body paragraph.", ("BodyTight",)).apply(document)
    assert outcome.status is Status.FAILED


def test_distinct_base_styles_never_share_a_derived_name() -> None:
    assert derived_style_name("Body Text") != derived_style_name("Body_Text")
    assert derived_style_name("x" * 60 + "a") != derived_style_name("x" * 60 + "b")
    assert derived_style_name("BodyTight").startswith("A11ySpacing_BodyTight_")


def test_the_generated_style_converges_when_the_reference_changes(tmp_path: Path) -> None:
    document = _spacing_document(tmp_path)
    operation = NormalizeSpacing("Body paragraph.", ("BodyTight",))
    assert statuses(operation, document) == (Status.APPLIED,)
    first = {
        style.get(qn("style", "name"))
        for style in select_elements(document.tree(Part.CONTENT), "//style:style")
        if "A11ySpacing" in (style.get(qn("style", "name")) or "")
    }
    select_elements(document.edit(Part.CONTENT), "//text:p")[0].set(
        qn("text", "style-name"), "Heading1"
    )
    assert statuses(operation, document) == (Status.APPLIED,)
    second = {
        style.get(qn("style", "name"))
        for style in select_elements(document.tree(Part.CONTENT), "//style:style")
        if "A11ySpacing" in (style.get(qn("style", "name")) or "")
    }
    assert first == second == {derived_style_name("BodyTight")}
