# SPDX-License-Identifier: MPL-2.0
"""Anchors resolve by declared identity, with explicit refusal to infer repairs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.families.text.references import audit_references
from odfa11y.odf import OdfDocument, Part
from odfa11y.remediation import SetMetadata
from odfa11y.source_audit import audit_odf
from tests.fixtures.documents import Variant, make_flat
from tests.fixtures.operations import execute_operations
from tests.fixtures.paths import TESTS

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('<text:p><text:bookmark text:name="a"/><text:a xlink:href="#a">Go</text:a></text:p>', []),
        (
            (
                '<text:p><text:a xlink:href="https://example.org" office:name="a">Target</text:a>'
                '<text:a xlink:href="#a">Go</text:a></text:p>'
            ),
            [],
        ),
        ('<text:p><text:a xlink:href="#missing">Go</text:a></text:p>', ["REFERENCE001"]),
        (
            (
                '<text:p><text:a office:name="a">One</text:a><text:a office:name="a">Two</text:a>'
                '<text:a xlink:href="#a">Go</text:a></text:p>'
            ),
            ["REFERENCE002"],
        ),
        (
            (
                '<text:p><text:bookmark-start text:name="a"/>A'
                '<text:bookmark-start text:name="b"/>B<text:bookmark-end text:name="a"/>'
                'C<text:bookmark-end text:name="b"/></text:p>'
            ),
            [],
        ),
        (
            (
                '<text:p><text:bookmark-end text:name="a"/>A'
                '<text:bookmark-start text:name="a"/></text:p>'
            ),
            ["REFERENCE003"],
        ),
        (
            (
                '<text:p><text:reference-mark text:name="a"/>'
                '<text:bookmark-ref text:ref-name="a" text:reference-format="text"/></text:p>'
            ),
            ["REFERENCE001"],
        ),
        (
            (
                '<text:p><text:reference-mark text:name="a"/>'
                '<text:reference-ref text:ref-name="a" text:reference-format="text"/></text:p>'
            ),
            [],
        ),
        (
            (
                '<text:p><text:note text:id="a" text:note-class="footnote">'
                "<text:note-citation>1</text:note-citation><text:note-body><text:p>Body</text:p>"
                '</text:note-body></text:note><text:note-ref text:ref-name="a" '
                'text:note-class="footnote" text:reference-format="text"/></text:p>'
            ),
            [],
        ),
        (
            (
                '<text:p><text:note text:id="a" text:note-class="footnote">'
                "<text:note-citation>1</text:note-citation><text:note-body/></text:note></text:p>"
            ),
            ["NOTE002"],
        ),
    ],
)
def test_relationship_controls(tmp_path: Path, body: str, expected: list[str]) -> None:
    source = make_flat(tmp_path, "text", Variant(body=f"<office:text>{body}</office:text>"))
    report = audit_odf(source)
    observed = [
        f.rule_id
        for f in report.findings
        if f.rule_id.startswith("REFERENCE") or f.rule_id == "NOTE002"
    ]
    assert observed == expected
    document = OdfDocument.open(source)
    checkpoint = document.checkpoint()
    audit_references(document, report)
    assert not document.changed_since(checkpoint)


@pytest.mark.parametrize("case", ["positive", "negative"])
def test_writer_relationship_fixtures(case: str) -> None:
    report = audit_odf(TESTS / "text_corpus" / f"references-{case}.odt")
    findings = [f.rule_id for f in report.findings if f.rule_id.startswith("REFERENCE")]
    assert findings == ([] if case == "positive" else ["REFERENCE001"])


@pytest.mark.parametrize(
    "body",
    [
        (
            '<text:section text:name="Hidden" text:display="none"><text:p>'
            '<text:bookmark text:name="a"/></text:p></text:section>'
            '<text:p><text:a xlink:href="#a">Go</text:a></text:p>'
        ),
        '<text:p><text:a xlink:href="#1.Heading|outline">Go</text:a></text:p>',
    ],
)
def test_excluded_and_producer_specific_targets_remain_explicit_review(
    tmp_path: Path, body: str
) -> None:
    report = audit_odf(
        make_flat(tmp_path, "text", Variant(body=f"<office:text>{body}</office:text>"))
    )
    assert [f.rule_id for f in report.findings if f.rule_id.startswith("REFERENCE")] == [
        "REFERENCE004"
    ]


def test_range_cannot_cross_note_reading_context(tmp_path: Path) -> None:
    body = (
        '<office:text><text:p><text:bookmark-start text:name="a"/>'
        '<text:note text:id="n1" text:note-class="footnote"><text:note-citation>1'
        '</text:note-citation><text:note-body><text:p>Note<text:bookmark-end text:name="a"/>'
        "</text:p></text:note-body></text:note></text:p></office:text>"
    )
    report = audit_odf(make_flat(tmp_path, "text", Variant(body=body)))
    finding = next(f for f in report.findings if f.rule_id == "REFERENCE003")
    assert finding.location is not None
    assert finding.location.path.startswith("content/reference[")


def test_duplicate_note_identities_are_reported_without_reference_fields(tmp_path: Path) -> None:
    note = (
        '<text:note text:id="n1" text:note-class="footnote"><text:note-citation>1'
        "</text:note-citation><text:note-body><text:p>Note body</text:p></text:note-body>"
        "</text:note>"
    )
    report = audit_odf(
        make_flat(
            tmp_path,
            "text",
            Variant(body=f"<office:text><text:p>{note}{note}</text:p></office:text>"),
        )
    )
    assert len([f for f in report.findings if f.rule_id == "NOTE002"]) == 2
    assert not any(
        rule.startswith("REFERENCE") or rule == "NOTE002"
        for question in report.decisions
        for rule in question.rule_ids
    )


@pytest.mark.parametrize("case", ["positive", "negative"])
def test_review_metadata_does_not_repair_or_retarget_references(tmp_path: Path, case: str) -> None:
    source = TESTS / "text_corpus" / f"references-{case}.odt"
    output = tmp_path / "reviewed.odt"
    before = etree.tostring(OdfDocument.open(source).tree(Part.CONTENT))
    execute_operations(source, output, [SetMetadata(title="Reviewed references")])
    assert etree.tostring(OdfDocument.open(output).tree(Part.CONTENT)) == before
    report = audit_odf(output)
    assert not any(
        rule.startswith("REFERENCE") or rule == "NOTE002"
        for question in report.decisions
        for rule in question.rule_ids
    )
