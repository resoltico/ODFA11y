# SPDX-License-Identifier: MPL-2.0
"""Alt text on spreadsheet frames, and the snapshot that guards what a sheet shows."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.adapter import Status
from odfa11y.audit import audit_odf
from odfa11y.content import GraphicDescription
from odfa11y.families.spreadsheet import (
    SetGraphicDescriptions,
    SetSheetNames,
    sheet_snapshot,
    sheets_preserved,
)
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate

from .spreadsheet_fixtures import LAYOUTS, make_spreadsheet, picture, row, sheet, text_cell

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.adapter import Operation

by_layout = pytest.mark.parametrize("layout", LAYOUTS)
SHEETS = (
    sheet("Logos", row(picture("Logo"), picture("Seal", href="Pictures/seal.png"))),
    sheet("Other", row(picture("Badge", href="Pictures/badge.png"))),
)


def open_sheets(directory: Path, layout: str, *sheets: str) -> OdfDocument:
    return OdfDocument.open(make_spreadsheet(directory, layout, *sheets))


def frame_text(document: OdfDocument, name: str) -> list[tuple[str, str | None]]:
    [frame] = select_elements(document.tree(Part.CONTENT), f"//draw:frame[@draw:name='{name}']")
    return [(etree.QName(child).localname, child.text) for child in frame]


def statuses(operation: Operation, document: OdfDocument) -> tuple[Status, ...]:
    return tuple(outcome.status for outcome in operation.apply(document))


@by_layout
def test_alt_text_is_applied_once_then_unchanged_and_stays_schema_valid(
    tmp_path: Path, layout: str
) -> None:
    document = open_sheets(tmp_path, layout, *SHEETS)
    before = validate(document)
    operation = SetGraphicDescriptions({"Logo": GraphicDescription("Logo", "The company logo")})
    assert statuses(operation, document) == (Status.APPLIED,)
    assert frame_text(document, "Logo") == [
        ("image", None),
        ("title", "Logo"),
        ("desc", "The company logo"),
    ]
    assert statuses(operation, document) == (Status.UNCHANGED,)
    assert document.edit_count == 2
    assert validate(document).count == before.count


@by_layout
def test_a_frame_is_addressed_by_its_name_its_image_path_or_its_file_name(
    tmp_path: Path, layout: str
) -> None:
    document = open_sheets(tmp_path, layout, *SHEETS)
    operation = SetGraphicDescriptions({
        "Logo": GraphicDescription("by name"),
        "Pictures/seal.png": GraphicDescription("by path"),
        "badge.png": GraphicDescription("by file"),
    })
    assert statuses(operation, document) == (Status.APPLIED,) * 3
    assert frame_text(document, "Seal")[1] == ("title", "by path")
    assert frame_text(document, "Badge")[1] == ("title", "by file")


@by_layout
def test_changed_text_is_applied_and_an_unset_field_is_left_alone(
    tmp_path: Path, layout: str
) -> None:
    document = open_sheets(tmp_path, layout, *SHEETS)
    SetGraphicDescriptions({"Logo": GraphicDescription("Old", "Described")}).apply(document)
    assert statuses(SetGraphicDescriptions({"Logo": GraphicDescription("New")}), document) == (
        Status.APPLIED,
    )
    assert frame_text(document, "Logo")[1:] == [("title", "New"), ("desc", "Described")]


@by_layout
def test_a_selector_that_matches_nothing_fails_everything_before_any_edit(
    tmp_path: Path, layout: str
) -> None:
    document = open_sheets(tmp_path, layout, *SHEETS)
    operation = SetGraphicDescriptions({
        "Logo": GraphicDescription("Fine"),
        "Nowhere": GraphicDescription("x"),
    })
    outcomes = operation.apply(document)
    assert [(o.status, o.key) for o in outcomes] == [(Status.FAILED, "Nowhere")]
    assert document.edit_count == 0
    assert frame_text(document, "Logo") == [("image", None)]


@by_layout
def test_a_fingerprint_binds_the_entry_to_the_frame_that_was_reviewed(
    tmp_path: Path, layout: str
) -> None:
    document = open_sheets(tmp_path, layout, *SHEETS)
    fingerprint = _audited_fingerprint(tmp_path, layout, "Logo")
    right = SetGraphicDescriptions({"Logo": GraphicDescription("Logo", fingerprint=fingerprint)})
    wrong = SetGraphicDescriptions({"Logo": GraphicDescription("Logo", fingerprint="0" * 12)})
    [outcome] = wrong.apply(document)
    assert outcome.status is Status.FAILED
    assert "no longer the object" in outcome.message
    assert document.edit_count == 0
    assert statuses(right, document) == (Status.APPLIED,)
    assert statuses(right, document) == (Status.UNCHANGED,)


def _audited_fingerprint(directory: Path, layout: str, frame: str) -> str:
    report = audit_odf(make_spreadsheet(directory, layout, *SHEETS))
    [finding] = [
        f for f in report.findings if f.rule_id == "SHEET005" and f.details["frame"] == frame
    ]
    return str(finding.details["fingerprint"])


def test_a_fingerprint_survives_a_sheet_rename_in_the_same_plan(tmp_path: Path) -> None:
    document = open_sheets(tmp_path, "package", *SHEETS)
    fingerprint = _audited_fingerprint(tmp_path, "package", "Badge")
    assert statuses(SetSheetNames({"Other": "Badges"}), document) == (Status.APPLIED,)
    entry = GraphicDescription("Badge", fingerprint=fingerprint)
    assert statuses(SetGraphicDescriptions({"Badge": entry}), document) == (Status.APPLIED,)


def test_the_same_name_on_a_moved_sheet_is_not_the_reviewed_frame(tmp_path: Path) -> None:
    fingerprint = _audited_fingerprint(tmp_path, "package", "Badge")
    moved = open_sheets(tmp_path, "flat", SHEETS[1], SHEETS[0])
    [outcome] = SetGraphicDescriptions({
        "Badge": GraphicDescription("x", fingerprint=fingerprint)
    }).apply(moved)
    assert outcome.status is Status.FAILED


@by_layout
def test_two_selectors_setting_different_text_on_one_frame_both_fail(
    tmp_path: Path, layout: str
) -> None:
    document = open_sheets(tmp_path, layout, *SHEETS)
    conflicting = SetGraphicDescriptions({
        "Logo": GraphicDescription("One"),
        "logo.png": GraphicDescription("Two"),
    })
    outcomes = conflicting.apply(document)
    assert {o.key for o in outcomes} == {"Logo", "logo.png"}
    assert {o.status for o in outcomes} == {Status.FAILED}
    agreeing = SetGraphicDescriptions({
        "Logo": GraphicDescription("Same"),
        "logo.png": GraphicDescription("Same", "Extra"),
    })
    assert statuses(agreeing, document) == (Status.APPLIED, Status.APPLIED)
    assert frame_text(document, "Logo")[1:] == [("title", "Same"), ("desc", "Extra")]


def test_the_operation_describes_itself_with_its_entries() -> None:
    operation = SetGraphicDescriptions({"Logo": GraphicDescription("T", None, "abc")})
    assert operation.as_dict() == {
        "operation": "set_graphic_descriptions",
        "entries": {"Logo": {"title": "T", "description": None, "fingerprint": "abc"}},
    }


@by_layout
def test_the_snapshot_binds_sheet_data_and_repeated_cell_positions(
    tmp_path: Path, layout: str
) -> None:
    repeated = row(
        text_cell("a"),
        "<table:table-cell table:number-columns-repeated='3'/>",
        text_cell("b"),
        attributes="table:number-rows-repeated='2'",
    )
    document = open_sheets(tmp_path, layout, sheet("Budget", repeated, row(text_cell("c"))))
    before = sheet_snapshot(document)
    assert before[0] == "sheet\tBudget"
    assert len(before) == 2
    assert before[1].startswith("content\t")
    cells = select_elements(document.tree(Part.CONTENT), "//table:table-cell")
    cells[1].set(qn("table", "number-columns-repeated"), "4")
    assert sheet_snapshot(document) != before


@by_layout
def test_alt_text_never_changes_the_snapshot(tmp_path: Path, layout: str) -> None:
    document = open_sheets(tmp_path, layout, *SHEETS)
    before = sheet_snapshot(document)
    SetGraphicDescriptions({"Logo": GraphicDescription("Title", "Description")}).apply(document)
    assert sheet_snapshot(document) == before


@by_layout
@pytest.mark.parametrize(
    "attribute",
    [
        ("office", "value"),
        ("table", "formula"),
        ("table", "number-rows-spanned"),
        ("xlink", "href"),
    ],
)
def test_the_snapshot_detects_data_and_reference_changes_without_changed_words(
    tmp_path: Path, layout: str, attribute: tuple[str, str]
) -> None:
    document = open_sheets(tmp_path, layout, sheet("Values", row(text_cell("Same words"))))
    before = sheet_snapshot(document)
    cell = select_elements(document.tree(Part.CONTENT), "//table:table-cell")[0]
    cell.set(qn(*attribute), "changed")
    assert not sheets_preserved(before, sheet_snapshot(document), 0)


def test_only_sheet_names_may_differ_between_snapshots() -> None:
    before = ("sheet\tA", "cell\t1,1\tx", "sheet\tB", "cell\t1,1\ty")
    renamed = ("sheet\tC", "cell\t1,1\tx", "sheet\tD", "cell\t1,1\ty")
    assert sheets_preserved(before, before, 0)
    assert sheets_preserved(before, renamed, 0)
    assert not sheets_preserved(before, renamed, 1)
    edited = ("sheet\tA", "cell\t1,1\tchanged", "sheet\tB", "cell\t1,1\ty")
    assert not sheets_preserved(before, edited, 0)
    assert not sheets_preserved(before, before[:2], 0)
    assert not sheets_preserved(before, (*before, "sheet\tC"), 0)
    moved = ("sheet\tA", "cell\t2,1\tx", "sheet\tB", "cell\t1,1\ty")
    assert not sheets_preserved(before, moved, 0)
    swapped = ("sheet\tA", "sheet\tB", "cell\t1,1\tx", "cell\t1,1\ty")
    assert not sheets_preserved(before, swapped, 0)
