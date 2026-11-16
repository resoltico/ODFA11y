# SPDX-License-Identifier: AGPL-3.0-only
"""Logical header axes keep grouped/repeated data and reject unsafe boundaries."""

from copy import deepcopy
lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest

from odfa11y.audit import audit_odf
from odfa11y.concepts import axis_count, header_count, table_fingerprint
from odfa11y.decisions.edit import Status
from odfa11y.errors import PlanError
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.rules import registry as rules
from tests.fixtures.answers import (
    apply_in_memory,
    header_answer,
    header_inputs,
)
from tests.fixtures.documents import Variant, make_flat, make_package
from tests.fixtures.operations import apply_answers

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
    operation = header_inputs({"Data": header_answer(rows=2, columns=1, fingerprint=fingerprint)})
    once, twice = tmp_path / ("once" + source.suffix), tmp_path / ("twice" + source.suffix)
    assert apply_answers(source, once, [operation]).changed
    assert not apply_answers(once, twice, [operation]).changed
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
    operation = header_inputs({"Data": header_answer(rows=2, columns=1)})
    assert apply_in_memory(doc, operation)[0].status is Status.APPLIED
    assert (
        apply_in_memory(doc, header_inputs({"Data": header_answer(rows=3)}))[0].status
        is Status.APPLIED
    )
    table = select_elements(doc.tree(Part.CONTENT), "//table:table")[0]
    assert header_count(table, "columns") == 1
    group = select_elements(table, "./table:table-row-group")[0]
    assert group.get(qn("table", "display")) == "false"
    assert validate(doc).count == 0


@pytest.mark.parametrize("axis", ["rows", "columns"])
def test_a_repeated_merged_cell_crossing_a_boundary_is_rejected(tmp_path: Path, axis: str) -> None:
    body = REPEATED.replace('office:value="7"', f'office:value="7" table:number-{axis}-spanned="2"')
    doc = OdfDocument.open(make_package(tmp_path, "text", Variant(body=body)))
    entry = header_answer(rows=4) if axis == "rows" else header_answer(columns=1)
    operation = header_inputs({"Data": entry})
    outcome = apply_in_memory(doc, operation)[0]
    assert outcome.status is Status.FAILED
    assert "merged cell crosses" in outcome.message
    assert not doc.dirty


def test_no_output_is_published_when_a_later_header_target_fails(tmp_path: Path) -> None:
    doc = OdfDocument.open(make_package(tmp_path, "text", Variant(body=REPEATED)))
    table = select_elements(doc.tree(Part.CONTENT), "//table:table")[0]
    second = deepcopy(table)
    second.set(qn("table", "name"), "Other")
    parent = table.getparent()
    assert parent is not None
    parent.append(second)
    source = doc.save(tmp_path / "two-tables.odt")
    before = source.read_bytes()
    destination = tmp_path / "refused.odt"
    operation = header_inputs({"Data": header_answer(columns=1), "Other": header_answer(rows=9)})
    result = apply_answers(source, destination, [operation])
    assert not result.published
    assert any(outcome.status is Status.FAILED for outcome in result.outcomes)
    assert source.read_bytes() == before
    assert not destination.exists()


def test_nonleading_header_bands_are_rejected_without_rewriting_groups(tmp_path: Path) -> None:
    body = REPEATED.replace('table:number-rows-repeated="5"', 'table:number-rows-repeated="1"')
    body = body.replace(
        "</table:table>",
        "<table:table-header-rows><table:table-row><table:table-cell/></table:table-row></table:table-header-rows></table:table>",
    )
    doc = OdfDocument.open(make_package(tmp_path, "text", Variant(body=body)))
    outcome = apply_in_memory(doc, header_inputs({"Data": header_answer(rows=1)}))[0]
    assert outcome.status is Status.FAILED
    assert "Non-leading" in outcome.message
    assert not doc.dirty


@pytest.mark.parametrize("attribute", ["value", "formula", "number-columns-spanned"])
def test_reviewed_fingerprint_detects_protected_cell_changes(
    tmp_path: Path, attribute: str
) -> None:
    doc = OdfDocument.open(make_package(tmp_path, "text", Variant(body=REPEATED)))
    table = select_elements(doc.tree(Part.CONTENT), "//table:table")[0]
    fingerprint = table_fingerprint(table)
    cell = select_elements(table, ".//table:table-cell")[0]
    cell.set(qn("office" if attribute == "value" else "table", attribute), "changed")
    operation = header_inputs({"Data": header_answer(columns=1, fingerprint=fingerprint)})
    checkpoint = doc.checkpoint()
    with pytest.raises(PlanError, match="fingerprint"):
        apply_in_memory(doc, operation)
    assert not doc.changed_since(checkpoint)


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
    outcome = apply_in_memory(doc, header_inputs({"Data": header_answer(rows=2)}))[0]
    assert outcome.status is Status.FAILED
    assert "duplicate structural" in outcome.message
    assert not doc.dirty


@pytest.mark.parametrize("repeat", ["0", "-2", "not-a-number"])
def test_audit_reports_unresolvable_repeat_counts(tmp_path: Path, repeat: str) -> None:
    body = REPEATED.replace('number-rows-repeated="5"', f'number-rows-repeated="{repeat}"')
    source = make_package(tmp_path, "text", Variant(body=body))
    findings = [f for f in audit_odf(source).findings if f.rule_id == rules.TABLE002.id]
    assert len(findings) == 1
    assert findings[0].severity.value == "error"
