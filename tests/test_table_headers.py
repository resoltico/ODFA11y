# SPDX-License-Identifier: MPL-2.0
"""Logical header axes keep grouped/repeated data and reject unsafe boundaries."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.adapter import Status
from odfa11y.audit import audit_odf
from odfa11y.content import axis_count, header_count, table_fingerprint
from odfa11y.families.text import MarkTableHeaders, TableHeaders
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.remediation import remediate

from .documents import Variant, make_flat, make_package

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

REPEATED = (
    '<office:text><table:table table:name="Data">'
    '<table:table-column table:number-columns-repeated="4"/>'
    '<table:table-row table:number-rows-repeated="5">'
    '<table:table-cell office:value-type="float" office:value="7">'
    "<text:p>Seven</text:p></table:table-cell>"
    '<table:table-cell table:number-columns-repeated="3"><text:p>Label</text:p>'
    "</table:table-cell></table:table-row></table:table></office:text>"
)


@pytest.mark.parametrize("make", [make_package, make_flat])
def test_both_axes_split_repeats_without_changing_logical_data(
    tmp_path: Path, make: Callable[[Path, str, Variant], Path]
) -> None:
    source = make(tmp_path, "text", Variant(body=REPEATED))
    before = OdfDocument.open(source)
    table = select_elements(before.tree(Part.CONTENT), "//table:table")[0]
    fingerprint = table_fingerprint(table)
    operation = MarkTableHeaders({"Data": TableHeaders(rows=2, columns=1, fingerprint=fingerprint)})
    once, twice = tmp_path / ("once" + source.suffix), tmp_path / ("twice" + source.suffix)
    assert remediate(source, once, [operation]).changed
    assert not remediate(once, twice, [operation]).changed
    result = OdfDocument.open(twice)
    table = select_elements(result.tree(Part.CONTENT), "//table:table")[0]
    assert (axis_count(table, "rows"), axis_count(table, "columns")) == (5, 4)
    assert (header_count(table, "rows"), header_count(table, "columns")) == (2, 1)
    assert table_fingerprint(table) == fingerprint
    assert validate(result).count == 0


def test_groups_keep_their_identity_and_a_missing_axis_keeps_its_header(tmp_path: Path) -> None:
    body = REPEATED.replace(
        "<table:table-row ", '<table:table-row-group table:display="false"><table:table-row '
    )
    body = body.replace("</table:table-row>", "</table:table-row></table:table-row-group>")
    doc = OdfDocument.open(make_package(tmp_path, "text", Variant(body=body)))
    operation = MarkTableHeaders({"Data": TableHeaders(rows=2, columns=1)})
    assert operation.apply(doc)[0].status is Status.APPLIED
    assert MarkTableHeaders({"Data": TableHeaders(rows=3)}).apply(doc)[0].status is Status.APPLIED
    table = select_elements(doc.tree(Part.CONTENT), "//table:table")[0]
    assert header_count(table, "columns") == 1
    group = select_elements(table, "./table:table-row-group")[0]
    assert group.get(qn("table", "display")) == "false"
    assert validate(doc).count == 0


@pytest.mark.parametrize("axis", ["rows", "columns"])
def test_a_repeated_merged_cell_crossing_a_boundary_is_rejected(tmp_path: Path, axis: str) -> None:
    body = REPEATED.replace('office:value="7"', f'office:value="7" table:number-{axis}-spanned="2"')
    doc = OdfDocument.open(make_package(tmp_path, "text", Variant(body=body)))
    entry = TableHeaders(rows=4) if axis == "rows" else TableHeaders(columns=1)
    operation = MarkTableHeaders({"Data": entry})
    outcome = operation.apply(doc)[0]
    assert outcome.status is Status.FAILED
    assert "merged cell crosses" in outcome.message
    assert doc.edit_count == 0


def test_no_earlier_table_is_mutated_when_a_later_target_fails(tmp_path: Path) -> None:
    doc = OdfDocument.open(make_package(tmp_path, "text", Variant(body=REPEATED)))
    table = select_elements(doc.tree(Part.CONTENT), "//table:table")[0]
    second = deepcopy(table)
    second.set(qn("table", "name"), "Other")
    parent = table.getparent()
    assert parent is not None
    parent.append(second)
    original = etree.tostring(doc.tree(Part.CONTENT))
    operation = MarkTableHeaders({"Data": TableHeaders(columns=1), "Other": TableHeaders(rows=9)})
    assert operation.apply(doc)[0].status is Status.FAILED
    assert etree.tostring(doc.tree(Part.CONTENT)) == original
    assert doc.edit_count == 0


def test_nonleading_header_bands_are_rejected_without_rewriting_groups(tmp_path: Path) -> None:
    body = REPEATED.replace('table:number-rows-repeated="5"', 'table:number-rows-repeated="1"')
    body = body.replace(
        "</table:table>",
        "<table:table-header-rows><table:table-row><table:table-cell/></table:table-row></table:table-header-rows></table:table>",
    )
    doc = OdfDocument.open(make_package(tmp_path, "text", Variant(body=body)))
    outcome = MarkTableHeaders({"Data": TableHeaders(rows=1)}).apply(doc)[0]
    assert outcome.status is Status.FAILED
    assert "Non-leading" in outcome.message
    assert doc.edit_count == 0


@pytest.mark.parametrize("attribute", ["value", "formula", "number-columns-spanned"])
def test_reviewed_fingerprint_detects_protected_cell_changes(
    tmp_path: Path, attribute: str
) -> None:
    doc = OdfDocument.open(make_package(tmp_path, "text", Variant(body=REPEATED)))
    table = select_elements(doc.tree(Part.CONTENT), "//table:table")[0]
    fingerprint = table_fingerprint(table)
    cell = select_elements(table, ".//table:table-cell")[0]
    cell.set(qn("office" if attribute == "value" else "table", attribute), "changed")
    operation = MarkTableHeaders({"Data": TableHeaders(columns=1, fingerprint=fingerprint)})
    assert operation.apply(doc)[0].status is Status.FAILED
    assert doc.edit_count == 0


@pytest.mark.parametrize(
    "structure",
    [
        '<text:h text:outline-level="1">Title</text:h>',
        '<draw:frame draw:name="Graphic"/>',
        '<text:p xml:id="word">Word</text:p>',
    ],
)
def test_repeat_splitting_rejects_duplicate_structural_identity(
    tmp_path: Path, structure: str
) -> None:
    body = REPEATED.replace("<text:p>Seven</text:p>", structure)
    doc = OdfDocument.open(make_package(tmp_path, "text", Variant(body=body)))
    outcome = MarkTableHeaders({"Data": TableHeaders(rows=2)}).apply(doc)[0]
    assert outcome.status is Status.FAILED
    assert "duplicate structural" in outcome.message
    assert doc.edit_count == 0


@pytest.mark.parametrize("repeat", ["0", "-2", "not-a-number"])
def test_audit_reports_unresolvable_repeat_counts(tmp_path: Path, repeat: str) -> None:
    body = REPEATED.replace('number-rows-repeated="5"', f'number-rows-repeated="{repeat}"')
    source = make_package(tmp_path, "text", Variant(body=body))
    findings = [f for f in audit_odf(source).findings if f.rule_id == "TXT022"]
    assert len(findings) == 1
    assert findings[0].severity.value == "error"
