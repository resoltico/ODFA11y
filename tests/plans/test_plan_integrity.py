# SPDX-License-Identifier: MPL-2.0
"""A plan must mean what its author reviewed: selector conflicts, fingerprints, style identity."""

from typing import Unpack
lazy from pathlib import Path

import pytest
from lxml import etree

from odfa11y.concepts import graphics_fingerprint, table_fingerprint
from odfa11y.decisions.edit import Status
from odfa11y.errors import PlanError
from odfa11y.families.text import derived_style_name
from odfa11y.odf import OdfDocument, Part, qn, select_elements
from tests.fixtures.answers import (
    Authored,
    apply_in_memory,
    graphic_answer,
    graphic_inputs,
    header_answer,
    header_inputs,
    spacing_input,
)
from tests.fixtures.writer import make_minimal_odt
lazy from tests.fixtures.writer import Features

WRONG = "0" * 16


def open_document(tmp_path: Path, **features: Unpack[Features]) -> OdfDocument:
    """Open a synthetic document with the given features.

    Returns
    -------
    OdfDocument
        The document.

    """
    return OdfDocument.open(make_minimal_odt(tmp_path / "doc.odt", features=features))


def statuses(operation: Authored, document: OdfDocument) -> tuple[Status, ...]:
    """Apply an operation and list its outcome statuses.

    Returns
    -------
    tuple[Status, ...]
        One status per outcome.

    """
    return tuple(outcome.status for outcome in apply_in_memory(document, operation))


def test_conflicting_alt_text_for_one_graphic_fails_every_involved_entry(tmp_path: Path) -> None:
    document = open_document(tmp_path, with_image_without_alt=True)
    entries = {
        "Logo": graphic_answer(description="A"),
        "content/frame[name=Logo]": graphic_answer(description="B"),
    }
    with pytest.raises(PlanError, match="same decision kind"):
        apply_in_memory(document, graphic_inputs(entries))
    assert not document.dirty


def test_entries_that_set_different_fields_or_equal_values_combine(tmp_path: Path) -> None:
    document = open_document(tmp_path, with_image_without_alt=True)
    combined = {"content/frame[name=Logo]": graphic_answer(title="T", description="D")}
    assert statuses(graphic_inputs(combined), document) == (Status.APPLIED,)
    assert statuses(graphic_inputs(combined), document) == (Status.UNCHANGED,)


def test_a_fingerprint_binds_alt_text_to_the_reviewed_graphic_and_survives_the_edit(
    tmp_path: Path,
) -> None:
    document = open_document(tmp_path, with_image_without_alt=True)
    frames = select_elements(document.tree(Part.CONTENT), "//draw:frame")
    fingerprint = graphics_fingerprint(document, frames)
    entry = {"Logo": graphic_answer("Title", "Description", fingerprint)}
    assert statuses(graphic_inputs(entry), document) == (Status.APPLIED,)
    assert (
        graphics_fingerprint(document, frames) == fingerprint
    )  # setting alt text does not change it
    assert statuses(graphic_inputs(entry), document) == (Status.UNCHANGED,)
    stale = {"Logo": graphic_answer("Other", fingerprint=WRONG)}
    checkpoint = document.checkpoint()
    with pytest.raises(PlanError, match="fingerprint"):
        apply_in_memory(document, graphic_inputs(stale))
    assert not document.changed_since(checkpoint)


def test_a_fingerprint_binds_header_rows_to_the_reviewed_table(tmp_path: Path) -> None:
    document = open_document(tmp_path, with_data_table=True)
    table = select_elements(document.tree(Part.CONTENT), "//table:table")[0]
    fingerprint = table_fingerprint(table)
    entry = {"Data": header_answer(1, fingerprint=fingerprint)}
    assert statuses(header_inputs(entry), document) == (Status.APPLIED,)
    assert table_fingerprint(table) == fingerprint  # moving rows into the header keeps it
    assert statuses(header_inputs(entry), document) == (Status.UNCHANGED,)


def test_a_table_that_drifted_since_review_is_refused(tmp_path: Path) -> None:
    document = open_document(tmp_path, with_data_table=True)
    table = select_elements(document.tree(Part.CONTENT), "//table:table")[0]
    fingerprint = table_fingerprint(table)
    select_elements(table, ".//text:p")[0].text = "Edited after review"
    checkpoint = document.checkpoint()
    with pytest.raises(PlanError, match="fingerprint"):
        apply_in_memory(
            document, header_inputs({"Data": header_answer(1, fingerprint=fingerprint)})
        )
    assert not document.changed_since(checkpoint)


def test_marking_headers_keeps_a_reviewed_graphic_in_that_row_addressable(tmp_path: Path) -> None:
    document = open_document(tmp_path, with_data_table=True, with_image_without_alt=True)
    frame = select_elements(document.tree(Part.CONTENT), "//draw:frame")[0]
    cell_paragraph = select_elements(document.tree(Part.CONTENT), "//table:table-cell/text:p")[0]
    cell_paragraph.append(frame)
    fingerprint = graphics_fingerprint(document, [frame])
    graphics = graphic_inputs({"Logo": graphic_answer("A logo", fingerprint=fingerprint)})
    assert statuses(graphics, document) == (Status.APPLIED,)
    assert statuses(header_inputs({"Data": header_answer(rows=1)}), document) == (Status.APPLIED,)
    assert graphics_fingerprint(document, [frame]) == fingerprint
    assert statuses(graphics, document) == (Status.UNCHANGED,)


def _spacing_document(tmp_path: Path) -> OdfDocument:
    document = open_document(tmp_path)
    paragraphs = select_elements(document.tree(Part.CONTENT), "//text:p")
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
    foreign = _add_style(document.tree(Part.CONTENT), "office:automatic-styles", name)
    before = etree.tostring(foreign)
    checkpoint = document.checkpoint()
    (outcome,) = apply_in_memory(document, spacing_input("Body paragraph.", ("BodyTight",)))
    assert outcome.status is Status.FAILED
    assert "not an unmodified derivation" in outcome.message
    assert etree.tostring(foreign) == before
    assert not document.changed_since(checkpoint)  # nothing was edited after the conflict was found


def test_a_foreign_style_in_the_styles_part_is_protected_too(tmp_path: Path) -> None:
    document = _spacing_document(tmp_path)
    name = derived_style_name("BodyTight")
    _add_style(document.tree(Part.STYLES), "office:styles", name)
    (outcome,) = apply_in_memory(document, spacing_input("Body paragraph.", ("BodyTight",)))
    assert outcome.status is Status.FAILED


def test_distinct_base_styles_never_share_a_derived_name() -> None:
    assert derived_style_name("Body Text") != derived_style_name("Body_Text")
    assert derived_style_name("x" * 60 + "a") != derived_style_name("x" * 60 + "b")
    assert derived_style_name("BodyTight").startswith("A11ySpacing_BodyTight_")


def test_the_generated_style_converges_when_the_reference_changes(tmp_path: Path) -> None:
    document = _spacing_document(tmp_path)
    operation = spacing_input("Body paragraph.", ("BodyTight",))
    assert statuses(operation, document) == (Status.APPLIED,)
    first = {
        style.get(qn("style", "name"))
        for style in select_elements(document.tree(Part.CONTENT), "//style:style")
        if "A11ySpacing" in (style.get(qn("style", "name")) or "")
    }
    select_elements(document.tree(Part.CONTENT), "//text:p")[0].set(
        qn("text", "style-name"), "Heading1"
    )
    assert statuses(operation, document) == (Status.APPLIED,)
    second = {
        style.get(qn("style", "name"))
        for style in select_elements(document.tree(Part.CONTENT), "//style:style")
        if "A11ySpacing" in (style.get(qn("style", "name")) or "")
    }
    assert first == second == {derived_style_name("BodyTight")}
