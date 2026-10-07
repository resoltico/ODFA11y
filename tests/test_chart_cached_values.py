# SPDX-License-Identifier: MPL-2.0
"""Chart consistency checks preserve gaps and inspect compressed ranges safely."""

from __future__ import annotations

from pathlib import Path

import pytest

from odfa11y.audit import audit_odf
from odfa11y.families.chart.ranges import resolve_range
from odfa11y.odf import OdfDocument, Part, qn, select_elements

SOURCE = Path(__file__).parent / "family_corpus/fruit-chart.odc"


@pytest.mark.parametrize("gap", ["empty", "nan", "covered", "whitespace"])
def test_intentional_series_gaps_do_not_imply_type_or_cardinality_mismatch(
    tmp_path: Path, gap: str
) -> None:
    document = OdfDocument.open(SOURCE)
    cell = select_elements(document.edit(Part.CONTENT), "//table:table-cell[@office:value]")[0]
    if gap == "nan":
        cell.set(qn("office", "value"), "NaN")
    else:
        cell.attrib.clear()
        cell[:] = []
        if gap == "whitespace":
            cell.set(qn("office", "value-type"), "string")
            cell.set(qn("office", "string-value"), "  ")
        if gap == "covered":
            cell.tag = qn("table", "covered-table-cell")
    report = audit_odf(document.save(tmp_path / "gap.odc"))
    assert "CHART006" not in {finding.rule_id for finding in report.findings}


def test_billion_value_series_is_checked_without_materializing_repeats(tmp_path: Path) -> None:
    document = OdfDocument.open(SOURCE)
    tree = document.edit(Part.CONTENT)
    row = select_elements(tree, "//table:table-rows/table:table-row")[0]
    row.set(qn("table", "number-rows-repeated"), "1000000000")
    categories = select_elements(tree, "//chart:categories")[0]
    categories.set(qn("table", "cell-range-address"), "local-table.$A$2:.$A$1000000001")
    series = select_elements(tree, "//chart:series")[0]
    series.set(qn("chart", "values-cell-range-address"), "local-table.$B$2:.$B$1000000001")
    chart = select_elements(tree, "//chart:chart")[0]
    resolved = resolve_range(chart, "local-table.$B$2:.$B$1000000001")
    assert resolved is not None
    assert resolved.shape == (1000000000, 1)
    assert len(list(resolved.cells())) == 1
    report = audit_odf(document.save(tmp_path / "repeated.odc"))
    assert "CHART006" not in {finding.rule_id for finding in report.findings}
    row[1].set(qn("office", "value-type"), "string")
    row[1].attrib.pop(qn("office", "value"))
    report = audit_odf(document.save(tmp_path / "nonnumeric.odc"))
    assert "CHART006" in {finding.rule_id for finding in report.findings}


def test_invalid_interior_row_cell_repeat_produces_range_finding_instead_of_crashing(
    tmp_path: Path,
) -> None:
    document = OdfDocument.open(SOURCE)
    tree = document.edit(Part.CONTENT)
    rows = select_elements(tree, "//table:table-rows/table:table-row")
    rows[0].set(qn("table", "number-rows-repeated"), "2")
    rows[0][1].set(qn("table", "number-columns-repeated"), "0")
    series = select_elements(tree, "//chart:series")[0]
    series.set(qn("chart", "values-cell-range-address"), "local-table.$B$1:.$B$4")
    report = audit_odf(document.save(tmp_path / "invalid.odc"))
    assert "CHART004" in {finding.rule_id for finding in report.findings}
