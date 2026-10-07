# SPDX-License-Identifier: MPL-2.0
"""Renaming sheets: explicit, fail-closed, collision-safe, and never at the cost of a reference."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odfa11y.adapter import Status
from odfa11y.families.spreadsheet import SetSheetNames, invalid_name_reason
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate

from .spreadsheet_fixtures import LAYOUTS, make_spreadsheet, row, sheet, text_cell

if TYPE_CHECKING:
    from pathlib import Path

by_layout = pytest.mark.parametrize("layout", LAYOUTS)
PLAIN = (sheet("Sheet1", row(text_cell("a"))), sheet("Notes", row(text_cell("b"))))


def open_sheets(directory: Path, layout: str, *sheets: str) -> OdfDocument:
    return OdfDocument.open(make_spreadsheet(directory, layout, *sheets))


def sheet_names(document: OdfDocument) -> list[str | None]:
    tables = select_elements(document.tree(Part.CONTENT), "//office:spreadsheet/table:table")
    return [table.get(qn("table", "name")) for table in tables]


def statuses(operation: SetSheetNames, document: OdfDocument) -> tuple[Status, ...]:
    return tuple(outcome.status for outcome in operation.apply(document))


def referencing(reference: str) -> str:
    """Write a sheet whose one cell carries a formula or link attribute value.

    Returns
    -------
    str
        A sheet named ``Calc``.

    """
    return sheet("Calc", row(text_cell("x", f'table:formula="{reference}"')))


@by_layout
def test_renames_apply_once_then_report_unchanged_and_stay_schema_valid(
    tmp_path: Path, layout: str
) -> None:
    document = open_sheets(tmp_path, layout, *PLAIN)
    before = validate(document)
    operation = SetSheetNames({"Sheet1": "Budget"})
    assert statuses(operation, document) == (Status.APPLIED,)
    assert sheet_names(document) == ["Budget", "Notes"]
    assert statuses(operation, document) == (Status.UNCHANGED,)
    assert document.edit_count == 1
    assert validate(document).count == before.count


@by_layout
def test_an_unknown_sheet_fails_the_whole_operation_before_any_edit(
    tmp_path: Path, layout: str
) -> None:
    document = open_sheets(tmp_path, layout, *PLAIN)
    outcomes = SetSheetNames({"Sheet1": "Budget", "Missing": "Other"}).apply(document)
    assert [(o.status, o.key) for o in outcomes] == [(Status.FAILED, "Missing")]
    assert "No unique sheet is named 'Missing'" in outcomes[0].message
    assert document.edit_count == 0
    assert sheet_names(document) == ["Sheet1", "Notes"]


@by_layout
def test_a_new_name_that_collides_with_another_sheet_is_refused_whatever_its_case(
    tmp_path: Path, layout: str
) -> None:
    document = open_sheets(tmp_path, layout, *PLAIN)
    for new in ("Notes", "notes"):
        outcomes = SetSheetNames({"Sheet1": new}).apply(document)
        assert outcomes[0].status is Status.FAILED
        assert "already named" in outcomes[0].message
    assert document.edit_count == 0


@by_layout
def test_a_rename_that_only_changes_case_is_allowed(tmp_path: Path, layout: str) -> None:
    document = open_sheets(tmp_path, layout, *PLAIN)
    assert statuses(SetSheetNames({"Notes": "NOTES"}), document) == (Status.APPLIED,)
    assert sheet_names(document) == ["Sheet1", "NOTES"]


@pytest.mark.parametrize(
    "new", ["", "   ", "a/b", "a[1]", "what?", "a:b", "a*b", "a\\b", "'a", "a'"]
)
def test_names_a_spreadsheet_application_rejects_are_refused(tmp_path: Path, new: str) -> None:
    assert invalid_name_reason(new)
    document = open_sheets(tmp_path, "package", *PLAIN)
    [outcome] = SetSheetNames({"Sheet1": new}).apply(document)
    assert outcome.status is Status.FAILED
    assert "not a usable sheet name" in outcome.message
    assert document.edit_count == 0


@pytest.mark.parametrize("new", ["Budget 2024", "It's", "Ünïcode", "1", "a.b"])
def test_ordinary_names_are_usable(new: str) -> None:
    assert invalid_name_reason(new) is None


@pytest.mark.parametrize(
    "entries",
    [
        {"Sheet1": "Notes", "Notes": "Sheet1"},
        {"Sheet1": "Notes", "Notes": "Other"},
        {"Sheet1": "Same", "Notes": "same"},
    ],
    ids=["swap", "chain", "shared target"],
)
def test_swaps_chains_and_shared_targets_are_refused(
    tmp_path: Path, entries: dict[str, str]
) -> None:
    document = open_sheets(tmp_path, "package", *PLAIN)
    outcomes = SetSheetNames(entries).apply(document)
    assert outcomes
    assert {o.status for o in outcomes} == {Status.FAILED}
    assert document.edit_count == 0


def test_two_sheets_with_one_name_cannot_be_addressed(tmp_path: Path) -> None:
    document = open_sheets(tmp_path, "package", *PLAIN, sheet("Notes"))
    [outcome] = SetSheetNames({"Notes": "Memo"}).apply(document)
    assert outcome.status is Status.FAILED
    assert "must be unique" in outcome.message


@by_layout
@pytest.mark.parametrize(
    "reference",
    [
        "of:=SUM([$Notes.A1:.A3])",
        "of:=[Notes.A1]",
        "of:=SUM([$Notes.A1:$Other.B2])",
        "of:=INDIRECT(&quot;Notes.A1&quot;)",
    ],
)
def test_a_sheet_a_formula_refers_to_by_name_is_not_renamed(
    tmp_path: Path, layout: str, reference: str
) -> None:
    document = open_sheets(tmp_path, layout, *PLAIN, referencing(reference))
    [outcome] = SetSheetNames({"Notes": "Memo"}).apply(document)
    assert outcome.status is Status.FAILED
    assert "may refer to it by name" in outcome.message
    assert document.edit_count == 0
    assert "Notes" in sheet_names(document)


def test_a_quoted_reference_to_a_sheet_with_a_space_or_apostrophe_is_found(tmp_path: Path) -> None:
    spaced = (sheet("My Data", row(text_cell("a"))), sheet("It's", row(text_cell("b"))))
    formula = referencing("of:=['My Data'.A1]+['It''s'.A1]")
    for old in ("My Data", "It's"):
        document = open_sheets(tmp_path, "package", *spaced, formula)
        [outcome] = SetSheetNames({old: "Renamed"}).apply(document)
        assert outcome.status is Status.FAILED, old


@pytest.mark.parametrize(
    "attribute",
    ['table:cell-range-address="Notes.A1:Notes.B2"', 'table:print-ranges="Notes.A1:Notes.B2"'],
)
def test_references_outside_formulas_block_the_rename_too(tmp_path: Path, attribute: str) -> None:
    document = open_sheets(
        tmp_path, "package", *PLAIN, sheet("Calc", row(text_cell("x", attribute)))
    )
    [outcome] = SetSheetNames({"Notes": "Memo"}).apply(document)
    assert outcome.status is Status.FAILED


@pytest.mark.parametrize("target", ["#Notes.A1", "#Notes"])
def test_a_link_to_a_sheet_blocks_its_rename(tmp_path: Path, target: str) -> None:
    link = f'<text:a xlink:href="{target}" xlink:type="simple">Notes</text:a>'
    document = open_sheets(tmp_path, "package", *PLAIN, sheet("Calc", row(text_cell(link))))
    [outcome] = SetSheetNames({"Notes": "Memo"}).apply(document)
    assert outcome.status is Status.FAILED


@by_layout
def test_references_to_other_sheets_do_not_block_an_unrelated_rename(
    tmp_path: Path, layout: str
) -> None:
    document = open_sheets(
        tmp_path, layout, *PLAIN, referencing("of:=SUM([$Notes.A1:.A3])+[.B1]+[$Other.C1]")
    )
    assert statuses(SetSheetNames({"Sheet1": "Budget"}), document) == (Status.APPLIED,)
    assert sheet_names(document)[:2] == ["Budget", "Notes"]


def test_a_document_with_embedded_charts_refuses_every_rename(tmp_path: Path) -> None:
    chart = (
        '<table:table-cell><draw:frame draw:name="Chart1" svg:width="1cm" svg:height="1cm">'
        '<draw:object xlink:href="./Object 1" xlink:type="simple"/></draw:frame></table:table-cell>'
    )
    document = open_sheets(tmp_path, "package", *PLAIN, sheet("Charts", row(chart)))
    [outcome] = SetSheetNames({"Sheet1": "Budget"}).apply(document)
    assert outcome.status is Status.FAILED
    assert "embeds charts" in outcome.message
    assert document.edit_count == 0


def test_a_failed_rename_is_reported_with_every_other_failure(tmp_path: Path) -> None:
    document = open_sheets(tmp_path, "package", *PLAIN)
    outcomes = SetSheetNames({"Gone": "A", "Sheet1": "b/c"}).apply(document)
    assert {o.key for o in outcomes} == {"Gone", "Sheet1"}
    assert {o.status for o in outcomes} == {Status.FAILED}


def test_the_operation_describes_itself_with_its_entries() -> None:
    assert SetSheetNames({"Sheet1": "Budget"}).as_dict() == {
        "operation": "set_sheet_names",
        "entries": {"Sheet1": "Budget"},
    }


@by_layout
@pytest.mark.parametrize("function", ["INDIRECT", "ADDRESS", "HYPERLINK"])
def test_dynamic_reference_functions_block_a_rename(
    tmp_path: Path, layout: str, function: str
) -> None:
    formula = referencing(f"of:={function}(&quot;Notes&quot;&amp;&quot;.A1&quot;)")
    document = open_sheets(tmp_path, layout, *PLAIN, formula)
    assert statuses(SetSheetNames({"Notes": "Memo"}), document) == (Status.FAILED,)
    assert document.edit_count == 0


def test_embedded_scripts_block_a_rename(tmp_path: Path) -> None:
    document = open_sheets(tmp_path, "package", *PLAIN)
    document.storage.write_member("Basic/Standard/Module1.xml", b"script")
    assert statuses(SetSheetNames({"Notes": "Memo"}), document) == (Status.FAILED,)
    assert document.edit_count == 0


def test_duplicate_targets_are_not_treated_as_a_completed_rename(tmp_path: Path) -> None:
    document = open_sheets(tmp_path, "package", sheet("Memo"), sheet("Memo"))
    assert statuses(SetSheetNames({"Notes": "Memo"}), document) == (Status.FAILED,)


@pytest.mark.parametrize("map_name", ["Tables", "ScriptConfiguration"])
def test_sheet_settings_follow_a_rename_without_changing_other_settings(
    tmp_path: Path, map_name: str
) -> None:
    document = open_sheets(tmp_path, "package", *PLAIN)
    namespace = "urn:oasis:names:tc:opendocument:xmlns:config:1.0"
    settings = (
        "<office:document-settings "
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        f'xmlns:config="{namespace}"><office:settings>'
        f'<config:config-item-map-named config:name="{map_name}">'
        '<config:config-item-map-entry config:name="Notes"/>'
        '<config:config-item-map-entry config:name="Sheet1"/>'
        "</config:config-item-map-named>"
        '<config:config-item config:name="ActiveTable" config:type="string">'
        "Notes</config:config-item>"
        '<config:config-item config:name="Other" config:type="string">Notes</config:config-item>'
        "</office:settings></office:document-settings>"
    )
    document.storage.write_member("settings.xml", settings.encode())
    assert statuses(SetSheetNames({"Notes": "Memo"}), document) == (Status.APPLIED,)
    tree = document.tree(Part.SETTINGS)
    assert tree.xpath(
        "//config:config-item-map-entry/@config:name", namespaces={"config": namespace}
    ) == ["Memo", "Sheet1"]
    assert tree.xpath(
        "//config:config-item[@config:name='ActiveTable']/text()", namespaces={"config": namespace}
    ) == ["Memo"]
    assert tree.xpath(
        "//config:config-item[@config:name='Other']/text()", namespaces={"config": namespace}
    ) == ["Notes"]
