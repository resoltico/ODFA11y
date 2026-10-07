# SPDX-License-Identifier: MPL-2.0
"""Each spreadsheet rule fires where it should and stays quiet where it should, in both layouts."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odfa11y.audit import audit_odf, render_template
from odfa11y.families import adapter_for
from odfa11y.odf import OdfDocument

from .documents import make_package
from .spreadsheet_fixtures import (
    HIDDEN_SHEET_STYLE,
    LAYOUTS,
    data_sheet,
    make_spreadsheet,
    picture,
    row,
    sheet,
    text_cell,
)

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.report import Finding, Report

by_layout = pytest.mark.parametrize("layout", LAYOUTS)
CONTENT = sheet("Budget", row(text_cell("Total"), text_cell("7")))
EMPTY = sheet("Spare", row("<table:table-cell/>"))
ALT = "<svg:title>Company logo</svg:title>"


def audit(directory: Path, layout: str, *sheets: str, styles: str = "") -> Report:
    return audit_odf(make_spreadsheet(directory, layout, *sheets, automatic_styles=styles))


def found(report: Report, rule_id: str) -> list[Finding]:
    return [finding for finding in report.findings if finding.rule_id == rule_id]


@by_layout
def test_a_clean_spreadsheet_has_no_spreadsheet_findings(tmp_path: Path, layout: str) -> None:
    report = audit(tmp_path, layout, data_sheet("Prices", header_rows=1))
    assert not [f for f in report.findings if f.rule_id.startswith("SHEET")]
    assert report.metadata["adapter"] == "spreadsheet"
    assert report.metadata["sheet_count"] == 1
    assert report.metadata["graphic_object_count"] == 0


@by_layout
def test_a_sheet_without_a_name_is_an_error(tmp_path: Path, layout: str) -> None:
    report = audit(tmp_path, layout, CONTENT, sheet(""))
    [finding] = found(report, "SHEET001")
    assert finding.severity.value == "error"
    assert finding.location is not None
    assert finding.location.endswith("sheet 2")
    assert not found(audit(tmp_path, layout, CONTENT), "SHEET001")


@by_layout
@pytest.mark.parametrize("name", ["Sheet1", "sheet 2", "SHEET12"])
def test_a_default_sheet_name_is_reported_with_its_remedy(
    tmp_path: Path, layout: str, name: str
) -> None:
    [finding] = found(audit(tmp_path, layout, sheet(name)), "SHEET002")
    assert finding.details == {"sheet": name}
    assert finding.remedy == "spreadsheet.sheet_names"


@by_layout
@pytest.mark.parametrize("name", ["Budget", "Sheets", "Sheet1a", "My Sheet 1"])
def test_a_chosen_sheet_name_is_not_reported(tmp_path: Path, layout: str, name: str) -> None:
    assert not found(audit(tmp_path, layout, sheet(name)), "SHEET002")


@by_layout
def test_a_data_sheet_without_header_rows_is_reported(tmp_path: Path, layout: str) -> None:
    report = audit(tmp_path, layout, data_sheet("Prices"), data_sheet("Costs", header_rows=1))
    [finding] = found(report, "SHEET003")
    assert finding.details == {"sheet": "Prices"}


@by_layout
def test_sheets_that_are_not_data_tables_need_no_header_rows(tmp_path: Path, layout: str) -> None:
    prose = "A long paragraph of prose is a layout cell, not a column label. " * 3
    report = audit(
        tmp_path,
        layout,
        sheet("Single", row(text_cell("Item"), text_cell("Amount"))),
        sheet("Narrative", row(text_cell(prose), text_cell("x")), row(text_cell("a"))),
        sheet("OneLabel", row(text_cell("Only")), row(text_cell("a"), text_cell("b"))),
    )
    assert not found(report, "SHEET003")


@by_layout
def test_merged_cells_in_a_data_sheet_are_reported(tmp_path: Path, layout: str) -> None:
    report = audit(
        tmp_path, layout, data_sheet("Prices", header_rows=1, merged=True), data_sheet("Costs")
    )
    [finding] = found(report, "SHEET004")
    assert finding.details == {"sheet": "Prices", "merged_cells": 1}


@by_layout
def test_a_merged_banner_outside_a_data_sheet_is_not_reported(tmp_path: Path, layout: str) -> None:
    banner = sheet("Cover", row(text_cell("Report", 'table:number-columns-spanned="2"')))
    assert not found(audit(tmp_path, layout, banner), "SHEET004")


@by_layout
def test_a_picture_without_accessible_text_is_an_error_with_a_fingerprinted_selector(
    tmp_path: Path, layout: str
) -> None:
    body = sheet("Logos", row(picture("Logo"), picture("Seal", alt=ALT)))
    report = audit(tmp_path, layout, body)
    [finding] = found(report, "SHEET005")
    assert finding.severity.value == "error"
    assert finding.remedy == "spreadsheet.alt_text"
    assert finding.details["frame"] == "Logo"
    assert finding.details["href"] == "Pictures/logo.png"
    assert len(str(finding.details["fingerprint"])) == 12
    assert report.metadata["graphic_object_count"] == 2


@by_layout
def test_a_description_alone_is_accessible_text(tmp_path: Path, layout: str) -> None:
    described = picture("Logo", alt="<svg:desc>Company logo</svg:desc>")
    assert not found(audit(tmp_path, layout, sheet("Logos", row(described))), "SHEET005")


@by_layout
@pytest.mark.parametrize(
    "text", ["https://example.org/a", "www.example.org", "mailto:a@example.org"]
)
def test_a_link_whose_text_is_its_address_is_reported(
    tmp_path: Path, layout: str, text: str
) -> None:
    link = f'<text:a xlink:href="{text}" xlink:type="simple">{text}</text:a>'
    report = audit(tmp_path, layout, sheet("Links", row(text_cell(link))))
    [finding] = found(report, "SHEET006")
    assert finding.details == {"text": text}


@by_layout
def test_a_link_with_descriptive_text_is_not_reported(tmp_path: Path, layout: str) -> None:
    link = '<text:a xlink:href="https://example.org/a" xlink:type="simple">Annual report</text:a>'
    assert not found(audit(tmp_path, layout, sheet("Links", row(text_cell(link)))), "SHEET006")


@by_layout
def test_empty_sheets_after_the_last_sheet_with_content_are_reported(
    tmp_path: Path, layout: str
) -> None:
    report = audit(tmp_path, layout, CONTENT, EMPTY, sheet("Extra"))
    assert [f.details["sheet"] for f in found(report, "SHEET007")] == ["Spare", "Extra"]


@by_layout
def test_an_empty_sheet_between_sheets_with_content_is_not_trailing(
    tmp_path: Path, layout: str
) -> None:
    assert not found(audit(tmp_path, layout, EMPTY, CONTENT), "SHEET007")


@by_layout
def test_a_sheet_holding_only_a_picture_is_not_empty(tmp_path: Path, layout: str) -> None:
    only_picture = sheet("Logos", row(picture("Logo", alt=ALT)))
    assert not found(audit(tmp_path, layout, CONTENT, only_picture), "SHEET007")


@by_layout
def test_a_document_of_empty_sheets_keeps_its_first_sheet(tmp_path: Path, layout: str) -> None:
    report = audit(tmp_path, layout, EMPTY, sheet("Extra"))
    assert [f.details["sheet"] for f in found(report, "SHEET007")] == ["Extra"]


@by_layout
def test_hidden_sheets_rows_and_columns_are_counted(tmp_path: Path, layout: str) -> None:
    hidden_row = row(text_cell("a"), text_cell("b"), attributes='table:visibility="collapse"')
    filtered = row(text_cell("c"), text_cell("d"), attributes='table:visibility="filter"')
    hidden_column = '<table:table-column table:visibility="collapse"/>'
    covered = sheet("Notes", row(text_cell("n")), style="taHidden")
    shown = sheet("Data", hidden_row, filtered, row(text_cell("e"), text_cell("f"))).replace(
        "<table:table-column/>", hidden_column, 1
    )
    report = audit(tmp_path, layout, covered, shown, styles=HIDDEN_SHEET_STYLE)
    [finding] = found(report, "SHEET008")
    assert finding.details == {"sheets": ["Notes"], "rows": 2, "columns": 1}


@by_layout
def test_visible_content_reports_no_hidden_findings(tmp_path: Path, layout: str) -> None:
    shown = sheet("Notes", row(text_cell("n")), style="taOther")
    visible_style = (
        '<style:style style:name="taOther" style:family="table">'
        '<style:table-properties table:display="true"/></style:style>'
    )
    assert not found(audit(tmp_path, layout, shown, styles=visible_style), "SHEET008")
    assert not found(audit(tmp_path, layout, shown), "SHEET008")


def test_a_sheet_style_hiding_one_sheet_does_not_hide_unstyled_sheets(tmp_path: Path) -> None:
    report = audit(tmp_path, "package", CONTENT, styles=HIDDEN_SHEET_STYLE)
    assert not found(report, "SHEET008")


def test_text_documents_never_produce_spreadsheet_rules(tmp_path: Path) -> None:
    report = audit_odf(make_package(tmp_path, "text"))
    assert not [f for f in report.findings if f.rule_id.startswith("SHEET")]
    assert report.metadata["adapter"] == "text"


def test_the_template_lists_each_decision_with_its_fingerprint(tmp_path: Path) -> None:
    body = sheet("Sheet1", row(picture("Logo")))
    path = make_spreadsheet(tmp_path, "package", body)
    template = render_template(audit_odf(path), adapter_for(OdfDocument.open(path).kind))
    assert '# [spreadsheet.sheet_names]\n# "Sheet1" = ""' in template
    assert '# [spreadsheet.alt_text."Logo"]' in template
    assert "# fingerprint = " in template
    assert all(line.startswith("#") or not line for line in template.splitlines())
