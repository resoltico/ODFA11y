# SPDX-License-Identifier: MPL-2.0
"""Revision and visibility relationships never authorize accepting or evaluating content."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.families.text import SetTargetLanguages, TargetLanguage
from odfa11y.families.text.language.effective import language_targets
from odfa11y.families.text.language.operations import language_fingerprint
from odfa11y.odf import OdfDocument, Part, select_elements
from odfa11y.remediation import SetMetadata
from odfa11y.report import FactKeys
from odfa11y.source_audit import audit_odf
from tests.fixtures.documents import Variant, make_flat
from tests.fixtures.operations import assert_refused, execute_operations

if TYPE_CHECKING:
    from pathlib import Path

INFO = "<office:change-info><dc:creator>Invented Author</dc:creator></office:change-info>"


def _region(kind: str = "insertion", identity: str = "r") -> str:
    return (
        f'<text:tracked-changes><text:changed-region xml:id="{identity}" text:id="{identity}">'
        f"<text:{kind}>{INFO}</text:{kind}></text:changed-region></text:tracked-changes>"
    )


@pytest.mark.parametrize(
    ("kind", "marks", "expected"),
    [
        (
            "insertion",
            '<text:change-start text:change-id="r"/>Words<text:change-end text:change-id="r"/>',
            [],
        ),
        (
            "format-change",
            '<text:change-start text:change-id="r"/>Words<text:change-end text:change-id="r"/>',
            [],
        ),
        ("deletion", '<text:change text:change-id="r"/>', []),
        (
            "insertion",
            '<text:change-end text:change-id="r"/>Words<text:change-start text:change-id="r"/>',
            ["REVISION002"],
        ),
        ("insertion", '<text:change-start text:change-id="r"/>', ["REVISION002"]),
        ("deletion", '<text:change text:change-id="missing"/>', ["REVISION002", "REVISION003"]),
        (
            "deletion",
            '<text:change text:change-id="r"/><text:change text:change-id="r"/>',
            ["REVISION002"],
        ),
        ("insertion", "No current mark.", ["REVISION003"]),
    ],
)
def test_revision_mark_relationship_controls(
    tmp_path: Path, kind: str, marks: str, expected: list[str]
) -> None:
    source = make_flat(
        tmp_path,
        "text",
        Variant(body=("<office:text>" + _region(kind) + f"<text:p>{marks}</text:p></office:text>")),
    )
    report = audit_odf(source)
    assert (
        sorted(f.rule_id for f in report.findings if f.rule_id in {"REVISION002", "REVISION003"})
        == expected
    )
    assert "REVISION001" in {f.rule_id for f in report.findings}


@pytest.mark.parametrize(
    ("field", "unresolved"),
    [
        (
            (
                '<text:hidden-text text:condition="true" text:string-value="Secret" '
                'text:is-hidden="false"/>'
            ),
            False,
        ),
        ('<text:hidden-text text:condition="true"/>', True),
        ('<text:hidden-paragraph text:condition=""/>', True),
        ('<text:hidden-paragraph text:condition="true" text:is-hidden="unknown"/>', True),
        (
            (
                '<text:conditional-text text:condition="unknownVariable" '
                'text:string-value-if-true="Yes" text:string-value-if-false="No"/>'
            ),
            False,
        ),
    ],
)
def test_cached_visibility_never_overrides_condition_scope(
    tmp_path: Path, field: str, *, unresolved: bool
) -> None:
    source = make_flat(
        tmp_path, "text", Variant(body=f"<office:text><text:p>{field}Body</text:p></office:text>")
    )
    report = audit_odf(source)
    assert "HIDDEN001" in {f.rule_id for f in report.findings}
    assert ("HIDDEN002" in {f.rule_id for f in report.findings}) is unresolved
    assert len(report.facts[FactKeys.TEXT_VISIBILITY_CONTEXTS]) == 1


def test_revision_title_edit_preserves_history_but_target_language_is_refused(
    tmp_path: Path,
) -> None:
    source = make_flat(
        tmp_path,
        "text",
        Variant(
            body=(
                "<office:text>" + _region() + '<text:p><text:change-start text:change-id="r"/>'
                'Inserted words<text:change-end text:change-id="r"/></text:p></office:text>'
            )
        ),
    )
    document = OdfDocument.open(source)
    before = etree.tostring(select_elements(document.tree(Part.CONTENT), "//office:body")[0])
    output = tmp_path / "metadata.fodt"
    assert execute_operations(source, output, [SetMetadata(title="Reviewed revisions")]).published
    assert (
        etree.tostring(
            select_elements(OdfDocument.open(output).tree(Part.CONTENT), "//office:body")[0]
        )
        == before
    )
    target, node = next(iter(language_targets(document).items()))
    unsafe = tmp_path / "unsafe.fodt"
    assert_refused(
        execute_operations(
            source,
            unsafe,
            [
                SetTargetLanguages({
                    target: TargetLanguage(
                        western="en", fingerprint=language_fingerprint(document, node)
                    )
                })
            ],
        ),
        match="Tracked revisions permit only",
    )
    assert not unsafe.exists()


@pytest.mark.parametrize(
    ("body", "styles", "expected"),
    [
        ('<text:p><draw:frame text:anchor-type="as-char"/></text:p>', "", None),
        ('<text:p><draw:frame text:anchor-type="paragraph"/></text:p>', "", "floating-frame"),
        ('<text:section text:name="Section"><text:p>Words</text:p></text:section>', "", "section"),
        (
            "<text:p>Words</text:p>",
            (
                '<style:style style:name="Columns" style:family="section">'
                '<style:section-properties><style:columns fo:column-count="2"/>'
                "</style:section-properties></style:style>"
            ),
            "multi-column",
        ),
    ],
)
def test_reading_order_uncertainty_has_explicit_declared_scope(
    tmp_path: Path, body: str, styles: str, expected: str | None
) -> None:
    report = audit_odf(
        make_flat(
            tmp_path,
            "text",
            Variant(body=f"<office:text>{body}</office:text>", automatic_styles=styles),
        )
    )
    findings = [f for f in report.findings if f.rule_id == "ORDER001"]
    assert [f.details["kind"] for f in findings] == ([] if expected is None else [expected])
    assert all("Declared layout" in str(f.details["scope"]) for f in findings)


def test_xml_identity_is_authoritative_and_must_agree_with_text_identity(tmp_path: Path) -> None:
    body = (
        "<office:text>"
        + _region("deletion").replace('text:id="r"', 'text:id="other"')
        + '<text:p><text:change text:change-id="r"/></text:p></office:text>'
    )
    report = audit_odf(make_flat(tmp_path, "text", Variant(body=body)))
    assert "REVISION002" in {finding.rule_id for finding in report.findings}
    assert report.facts[FactKeys.TEXT_REVISION_RELATIONSHIPS]["unresolved"] == 1


def test_conditionally_hidden_anchor_remains_unestablished_current_flow(tmp_path: Path) -> None:
    body = (
        "<office:text>"
        + _region("deletion")
        + '<text:section text:name="Hidden" text:display="none"><text:p>'
        '<text:change text:change-id="r"/></text:p></text:section></office:text>'
    )
    report = audit_odf(make_flat(tmp_path, "text", Variant(body=body)))
    assert {"REVISION001", "REVISION003", "HIDDEN001"} <= {f.rule_id for f in report.findings}
    assert "REVISION002" not in {finding.rule_id for finding in report.findings}


def test_note_range_cannot_end_in_another_reading_context(tmp_path: Path) -> None:
    body = (
        "<office:text>" + _region() + '<text:p><text:change-start text:change-id="r"/>Main'
        '<text:note text:id="n" text:note-class="footnote"><text:note-citation>1'
        "</text:note-citation><text:note-body><text:p>Note"
        '<text:change-end text:change-id="r"/></text:p></text:note-body></text:note>'
        "</text:p></office:text>"
    )
    report = audit_odf(make_flat(tmp_path, "text", Variant(body=body)))
    assert "REVISION002" in {finding.rule_id for finding in report.findings}
