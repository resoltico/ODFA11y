# SPDX-License-Identifier: MPL-2.0
"""Classify declared table relationships without inferring intent from visual typography."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odfa11y.families.text import MarkTableHeaders, TableHeaders
from odfa11y.families.text.tables.classification import TableKind, classify
from odfa11y.odf import OdfDocument, Part, select_elements, validate
from odfa11y.report import FactKeys
from odfa11y.source_audit import audit_odf
from tests.fixtures.documents import Variant, make_flat
from tests.fixtures.operations import assert_refused, execute_operations
from tests.fixtures.paths import TESTS

if TYPE_CHECKING:
    from pathlib import Path

CELL = "<table:table-cell><text:p>Label</text:p></table:table-cell>"
COMPLEX = (
    '<table:table table:name="Fruit"><table:table-column table:number-columns-repeated="3"/>'
    "<table:table-header-rows><table:table-row>"
    '<table:table-cell table:number-columns-spanned="2"><text:p>Fruit categories</text:p>'
    "</table:table-cell><table:covered-table-cell/>" + CELL + "</table:table-row>"
    "<table:table-row>" + CELL * 3 + "</table:table-row></table:table-header-rows>"
    "<table:table-row>"
    + CELL
    * 2
    + '<table:table-cell office:value-type="float" office:value="3"><text:p>3</text:p>'
    "</table:table-cell></table:table-row></table:table>"
)


def test_valid_merged_grid_with_semantic_bands_is_complex_data(tmp_path: Path) -> None:
    source = make_flat(tmp_path, "text", Variant(body=f"<office:text>{COMPLEX}</office:text>"))
    document = OdfDocument.open(source)
    assert validate(document).count == 0
    table = select_elements(document.tree(Part.CONTENT), "//table:table")[0]
    classified = classify(table)
    assert classified.kind is TableKind.COMPLEX_DATA
    assert classified.grid.rows == classified.grid.columns == 3
    assert classified.header_rows == 2
    report = audit_odf(source)
    assert not any(
        finding.rule_id in {"TABLE001", "TABLE002", "TABLE003"} for finding in report.findings
    )


@pytest.mark.parametrize("columns", [1, 2])
def test_untyped_visual_labels_do_not_establish_data_intent(tmp_path: Path, columns: int) -> None:
    table = (
        '<table:table table:name="Layout">'
        f'<table:table-column table:number-columns-repeated="{columns}"/>'
        '<table:table-row table:number-rows-repeated="2">'
        + CELL * columns
        + "</table:table-row></table:table>"
    )
    source = make_flat(tmp_path, "text", Variant(body=f"<office:text>{table}</office:text>"))
    report = audit_odf(source)
    expected = "layout-candidate" if columns == 1 else "ambiguous"
    assert report.facts[FactKeys.TEXT_TABLE_CLASSIFICATIONS][0]["classification"] == expected
    assert "TABLE001" in {finding.rule_id for finding in report.findings}
    assert not any(question.kind.id == "table.headers" for question in report.decisions)
    output = tmp_path / "refused.fodt"
    assert_refused(
        execute_operations(source, output, [MarkTableHeaders({"Layout": TableHeaders(rows=1)})]),
        match="ambiguous.*Writer",
    )
    assert not output.exists()


@pytest.mark.parametrize(
    "body",
    [
        COMPLEX.replace("<table:covered-table-cell/>", CELL),
        COMPLEX.replace('number-columns-spanned="2"', 'number-columns-spanned="4"'),
        COMPLEX.replace('number-columns-spanned="2"', 'number-columns-spanned="1"'),
    ],
)
def test_missing_or_orphan_coverage_is_a_relationship_error(tmp_path: Path, body: str) -> None:
    source = make_flat(tmp_path, "text", Variant(body=f"<office:text>{body}</office:text>"))
    assert "TABLE002" in {finding.rule_id for finding in audit_odf(source).findings}


def test_merged_origin_crossing_actual_header_band_requires_native_review(tmp_path: Path) -> None:
    body = (
        '<table:table table:name="Cross"><table:table-column/>'
        '<table:table-header-rows><table:table-row><table:table-cell table:number-rows-spanned="2">'
        "<text:p>Header and data?</text:p></table:table-cell></table:table-row>"
        "</table:table-header-rows><table:table-row><table:covered-table-cell/>"
        "</table:table-row></table:table>"
    )
    report = audit_odf(
        make_flat(tmp_path, "text", Variant(body=f"<office:text>{body}</office:text>"))
    )
    assert "TABLE001" in {finding.rule_id for finding in report.findings}
    assert "TABLE002" not in {finding.rule_id for finding in report.findings}


def test_grouped_headers_are_valid_complex_relationships(tmp_path: Path) -> None:
    body = (
        '<table:table table:name="Groups"><table:table-column/>'
        "<table:table-row-group><table:table-header-rows><table:table-row>"
        + CELL
        + "</table:table-row></table:table-header-rows><table:table-row>"
        + CELL
        + "</table:table-row></table:table-row-group><table:table-row-group>"
        "<table:table-header-rows><table:table-row>"
        + CELL
        + "</table:table-row></table:table-header-rows><table:table-row>"
        + CELL
        + "</table:table-row></table:table-row-group></table:table>"
    )
    source = make_flat(tmp_path, "text", Variant(body=f"<office:text>{body}</office:text>"))
    document = OdfDocument.open(source)
    assert validate(document).count == 0
    assert classify(select_elements(document.tree(Part.CONTENT), "//table:table")[0]).kind is (
        TableKind.COMPLEX_DATA
    )
    assert "TABLE002" not in {finding.rule_id for finding in audit_odf(source).findings}


def test_ambiguous_historical_writer_table_refuses_header_inference(tmp_path: Path) -> None:
    source = TESTS / "corpus/table-no-header-row.odt"
    output = tmp_path / "refused.odt"
    assert_refused(
        execute_operations(source, output, [MarkTableHeaders({"Table1": TableHeaders(rows=1)})]),
        match="ambiguous.*Writer",
    )
    assert not output.exists()


def test_large_simple_repeats_stay_arithmetic_and_complex_expansion_is_bounded(
    tmp_path: Path,
) -> None:
    simple = (
        '<table:table table:name="Large"><table:table-column/>'
        '<table:table-row table:number-rows-repeated="1000000000000">'
        '<table:table-cell office:value-type="float" office:value="3"><text:p>3</text:p>'
        "</table:table-cell></table:table-row></table:table>"
    )
    source = make_flat(tmp_path, "text", Variant(body=f"<office:text>{simple}</office:text>"))
    report = audit_odf(source)
    assert report.facts[FactKeys.TEXT_TABLE_CLASSIFICATIONS][0]["rows"] == 1000000000000
    assert "TABLE003" in {finding.rule_id for finding in report.findings}
    complex_grid = (
        '<table:table table:name="Large"><table:table-column table:number-columns-repeated="2"/>'
        '<table:table-row table:number-rows-repeated="100001">'
        '<table:table-cell table:number-columns-spanned="2"><text:p>Span</text:p>'
        "</table:table-cell><table:covered-table-cell/></table:table-row></table:table>"
    )
    second = make_flat(tmp_path, "text", Variant(body=f"<office:text>{complex_grid}</office:text>"))
    finding = next(f for f in audit_odf(second).findings if f.rule_id == "TABLE002")
    assert "bounded inspection" in finding.message
