# SPDX-License-Identifier: MPL-2.0
"""List relationships are inspected without changing authored typography or content."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odfa11y.families.text.lists import audit_lists
from odfa11y.odf import OdfDocument, Part, select_elements
from odfa11y.report import FactKeys
from odfa11y.source_audit import audit_odf
from tests.fixtures.documents import Variant, make_flat
from tests.fixtures.paths import TESTS

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.report import Report

ITEM = "<text:list-item><text:p>Apples</text:p></text:list-item>"


def _inspect(tmp_path: Path, body: str) -> Report:
    return audit_odf(
        make_flat(tmp_path, "text", Variant(body=f"<office:text>{body}</office:text>"))
    )


@pytest.mark.parametrize(
    ("body", "rule"),
    [
        ("<text:list><text:p>Not an item</text:p></text:list>", "LIST001"),
        (f"<text:list>{ITEM}<text:list-header/></text:list>", "LIST001"),
        ('<text:list text:continue-numbering="yes">' + ITEM + "</text:list>", "LIST001"),
        ('<text:list text:continue-list="missing">' + ITEM + "</text:list>", "LIST002"),
        ('<text:list xml:id="self" text:continue-list="self">' + ITEM + "</text:list>", "LIST002"),
        ('<text:list text:continue-numbering="true">' + ITEM + "</text:list>", "LIST003"),
        ("<text:p>1. Apples</text:p>", "LIST004"),
    ],
)
def test_invalid_and_review_relationship_controls(tmp_path: Path, body: str, rule: str) -> None:
    assert rule in {finding.rule_id for finding in _inspect(tmp_path, body).findings}


def test_explicit_continuation_overrides_false_and_accepts_acyclic_forward_reference(
    tmp_path: Path,
) -> None:
    report = _inspect(
        tmp_path,
        '<text:list text:continue-numbering="false" text:continue-list="later">'
        + ITEM
        + '</text:list><text:list xml:id="later">'
        + ITEM
        + "</text:list>",
    )
    assert not [f for f in report.findings if f.rule_id.startswith("LIST")]
    assert report.facts[FactKeys.TEXT_LIST_CONTINUATION_COUNT] == 1


def test_cycles_report_every_member_but_not_its_dependants(tmp_path: Path) -> None:
    report = _inspect(
        tmp_path,
        "".join(
            f'<text:list xml:id="{name}" text:continue-list="{target}">{ITEM}</text:list>'
            for name, target in [("a", "b"), ("b", "a"), ("c", "a")]
        ),
    )
    assert len([f for f in report.findings if f.rule_id == "LIST002"]) == 2


def test_duplicate_identity_with_non_list_owner(tmp_path: Path) -> None:
    source = make_flat(
        tmp_path,
        "text",
        Variant(
            body='<office:text><text:p xml:id="target">Intro</text:p>'
            '<text:list xml:id="other">' + ITEM + "</text:list>"
            '<text:list text:continue-list="target">' + ITEM + "</text:list></office:text>"
        ),
    )
    report = audit_odf(source)
    document = OdfDocument.open(source)
    select_elements(document.tree(Part.CONTENT), "//text:list")[0].set(
        "{http://www.w3.org/XML/1998/namespace}id", "target"
    )
    audit_lists(document, report)
    assert {"LIST001", "LIST002"} <= {f.rule_id for f in report.findings}


def test_table_cells_reset_nesting_and_do_not_share_implicit_counters(tmp_path: Path) -> None:
    report = _inspect(
        tmp_path,
        '<text:list text:style-name="Numbers"><text:list-item><table:table><table:table-row>'
        '<table:table-cell><text:list text:style-name="Numbers">'
        + ITEM
        + "</text:list></table:table-cell><table:table-cell>"
        '<text:list text:style-name="Numbers" text:continue-numbering="true">'
        + ITEM
        + "</text:list></table:table-cell></table:table-row></table:table>"
        "</text:list-item></text:list>",
    )
    assert report.facts[FactKeys.TEXT_LIST_MAX_LEVEL] == 1
    assert report.facts[FactKeys.TEXT_LIST_CONTINUATION_COUNT] == 0
    assert len([f for f in report.findings if f.rule_id == "LIST003"]) == 1


@pytest.mark.parametrize("case", ["positive", "negative"])
def test_writer_list_fixtures_and_read_only_preservation(case: str) -> None:
    source = TESTS / "text_corpus" / f"lists-{case}.odt"
    report = audit_odf(source)
    findings = [f.rule_id for f in report.findings if f.rule_id.startswith("LIST")]
    assert findings == ([] if case == "positive" else ["LIST004", "LIST004"])
    document = OdfDocument.open(source)
    checkpoint = document.checkpoint()
    audit_lists(document, report)
    assert not document.changed_since(checkpoint)
    assert report.facts[FactKeys.TEXT_LIST_COUNT] == (3 if case == "positive" else 0)
    assert report.facts[FactKeys.TEXT_LIST_MAX_LEVEL] == (2 if case == "positive" else 0)


def test_implicit_continuation_resolves_same_style_and_nested_level(tmp_path: Path) -> None:
    report = _inspect(
        tmp_path,
        '<text:list text:style-name="Numbers">' + ITEM + "</text:list>"
        '<text:list text:style-name="Numbers" text:continue-numbering="true">'
        + ITEM
        + "</text:list>",
    )
    assert not [f for f in report.findings if f.rule_id.startswith("LIST")]
    assert report.facts[FactKeys.TEXT_LIST_CONTINUATION_COUNT] == 1


def test_explicit_continuation_across_cells_requires_native_review(tmp_path: Path) -> None:
    report = _inspect(
        tmp_path,
        '<table:table><table:table-row><table:table-cell><text:list xml:id="a">'
        + ITEM
        + "</text:list></table:table-cell><table:table-cell>"
        '<text:list text:continue-list="a">'
        + ITEM
        + "</text:list></table:table-cell></table:table-row></table:table>",
    )
    assert [f.rule_id for f in report.findings if f.rule_id.startswith("LIST")] == ["LIST003"]


@pytest.mark.parametrize("body", ["<text:list/>", "<text:list><text:list-header/></text:list>"])
def test_empty_and_header_only_lists_are_permitted(tmp_path: Path, body: str) -> None:
    report = _inspect(tmp_path, body)
    assert not [f for f in report.findings if f.rule_id.startswith("LIST")]
