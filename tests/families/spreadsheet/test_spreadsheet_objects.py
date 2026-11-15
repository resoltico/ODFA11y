# SPDX-License-Identifier: MPL-2.0
"""Alt text on spreadsheet frames, and the snapshot that guards what a sheet shows."""

from pathlib import Path

import pytest
from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.decisions.edit import Status
from odfa11y.errors import PlanError
from odfa11y.families.spreadsheet import sheet_snapshot, sheets_preserved
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.targets import TargetPath, require_target
from tests.fixtures.answers import (
    Authored,
    graphic_answer,
    graphic_inputs,
)
from tests.fixtures.plans import question_for
from tests.fixtures.spreadsheets import (
    LAYOUTS,
    make_spreadsheet,
    picture,
    reviewed_sheet_names,
    row,
    sheet,
    text_cell,
)
lazy from tests.fixtures.answers import apply_in_memory

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


def statuses(operation: Authored, document: OdfDocument) -> tuple[Status, ...]:
    return tuple(outcome.status for outcome in apply_in_memory(document, operation))


@by_layout
def test_alt_text_is_applied_once_then_unchanged_and_stays_schema_valid(
    tmp_path: Path, layout: str
) -> None:
    document = open_sheets(tmp_path, layout, *SHEETS)
    before = validate(document)
    operation = graphic_inputs({"Logo": graphic_answer("Logo", "The company logo")})
    assert statuses(operation, document) == (Status.APPLIED,)
    assert frame_text(document, "Logo") == [
        ("image", None),
        ("title", "Logo"),
        ("desc", "The company logo"),
    ]
    assert statuses(operation, document) == (Status.UNCHANGED,)
    assert document.dirty == frozenset({document.member_name(Part.CONTENT)})
    assert validate(document).count == before.count


@by_layout
def test_a_frame_is_addressed_by_its_name_its_image_path_or_its_file_name(
    tmp_path: Path, layout: str
) -> None:
    document = open_sheets(tmp_path, layout, *SHEETS)
    operation = graphic_inputs({
        "content/sheet[1]/frame[name=Logo]": graphic_answer("Logo title"),
        "content/sheet[1]/frame[name=Seal]": graphic_answer("Seal title"),
        "content/sheet[2]/frame[name=Badge]": graphic_answer("Badge title"),
    })
    assert statuses(operation, document) == (Status.APPLIED,) * 3
    for selector in ("Logo", "Pictures/seal.png", "badge.png"):
        with pytest.raises(PlanError, match="target"):
            TargetPath(selector)
    assert frame_text(document, "Logo")[1] == ("title", "Logo title")
    assert frame_text(document, "Seal")[1] == ("title", "Seal title")
    assert frame_text(document, "Badge")[1] == ("title", "Badge title")


@by_layout
def test_changed_text_is_applied_and_an_unset_field_is_left_alone(
    tmp_path: Path, layout: str
) -> None:
    document = open_sheets(tmp_path, layout, *SHEETS)
    apply_in_memory(document, graphic_inputs({"Logo": graphic_answer("Old", "Described")}))
    assert statuses(graphic_inputs({"Logo": graphic_answer("New")}), document) == (Status.APPLIED,)
    assert frame_text(document, "Logo")[1:] == [("title", "New"), ("desc", "Described")]


@by_layout
def test_a_selector_that_matches_nothing_fails_everything_before_any_edit(
    tmp_path: Path, layout: str
) -> None:
    document = open_sheets(tmp_path, layout, *SHEETS)
    operation = graphic_inputs({
        "Logo": graphic_answer("Fine"),
        "Nowhere": graphic_answer("x"),
    })
    with pytest.raises(PlanError, match="exactly one"):
        apply_in_memory(document, operation)
    assert not document.dirty
    assert frame_text(document, "Logo") == [("image", None)]


@by_layout
def test_a_fingerprint_binds_the_entry_to_the_frame_that_was_reviewed(
    tmp_path: Path, layout: str
) -> None:
    document = open_sheets(tmp_path, layout, *SHEETS)
    fingerprint = _audited_fingerprint(tmp_path, layout, "Logo")
    right = graphic_inputs({"Logo": graphic_answer("Logo", fingerprint=fingerprint)})
    wrong = graphic_inputs({"Logo": graphic_answer("Logo", fingerprint="0" * 16)})
    with pytest.raises(PlanError, match="fingerprint"):
        apply_in_memory(document, wrong)
    assert not document.dirty
    assert statuses(right, document) == (Status.APPLIED,)
    assert statuses(right, document) == (Status.UNCHANGED,)


def _audited_fingerprint(directory: Path, layout: str, frame: str) -> str:
    report = audit_odf(make_spreadsheet(directory, layout, *SHEETS))
    [finding] = [
        f for f in report.findings if f.rule_id == "GRAPHIC003" and f.details["frame"] == frame
    ]
    return str(require_target(question_for(report, finding).target).fingerprint)


def test_a_fingerprint_survives_a_sheet_rename_in_the_same_plan(tmp_path: Path) -> None:
    document = open_sheets(tmp_path, "package", *SHEETS)
    fingerprint = _audited_fingerprint(tmp_path, "package", "Badge")
    assert statuses(reviewed_sheet_names(document, {"Other": "Badges"}), document) == (
        Status.APPLIED,
    )
    entry = graphic_answer("Badge", fingerprint=fingerprint)
    assert statuses(graphic_inputs({"Badge": entry}), document) == (Status.APPLIED,)


def test_the_same_name_on_a_moved_sheet_is_not_the_reviewed_frame(tmp_path: Path) -> None:
    fingerprint = _audited_fingerprint(tmp_path, "package", "Badge")
    moved = open_sheets(tmp_path, "flat", SHEETS[1], SHEETS[0])
    checkpoint = moved.checkpoint()
    with pytest.raises(PlanError, match="fingerprint"):
        apply_in_memory(
            moved, graphic_inputs({"Badge": graphic_answer("x", fingerprint=fingerprint)})
        )
    assert not moved.changed_since(checkpoint)


@by_layout
def test_two_selectors_setting_different_text_on_one_frame_both_fail(
    tmp_path: Path, layout: str
) -> None:
    document = open_sheets(tmp_path, layout, *SHEETS)
    conflicting = graphic_inputs({
        "Logo": graphic_answer("One"),
        "content/sheet[1]/frame[name=Logo]": graphic_answer("Two"),
    })
    with pytest.raises(PlanError, match="same decision kind"):
        apply_in_memory(document, conflicting)
    assert not document.dirty
    combined = graphic_inputs({
        "content/sheet[1]/frame[name=Logo]": graphic_answer("Same", "Extra")
    })
    assert statuses(combined, document) == (Status.APPLIED,)
    assert frame_text(document, "Logo")[1:] == [("title", "Same"), ("desc", "Extra")]


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
    apply_in_memory(document, graphic_inputs({"Logo": graphic_answer("Title", "Description")}))
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
    assert not sheets_preserved(before, sheet_snapshot(document))


def test_only_sheet_names_may_differ_between_snapshots() -> None:
    before = ("sheet\tA", "cell\t1,1\tx", "sheet\tB", "cell\t1,1\ty")
    renamed = ("sheet\tC", "cell\t1,1\tx", "sheet\tD", "cell\t1,1\ty")
    assert sheets_preserved(before, before)
    assert sheets_preserved(before, renamed)
    edited = ("sheet\tA", "cell\t1,1\tchanged", "sheet\tB", "cell\t1,1\ty")
    assert not sheets_preserved(before, edited)
    assert not sheets_preserved(before, before[:2])
    assert not sheets_preserved(before, (*before, "sheet\tC"))
    moved = ("sheet\tA", "cell\t2,1\tx", "sheet\tB", "cell\t1,1\ty")
    assert not sheets_preserved(before, moved)
    swapped = ("sheet\tA", "sheet\tB", "cell\t1,1\tx", "cell\t1,1\ty")
    assert not sheets_preserved(before, swapped)
