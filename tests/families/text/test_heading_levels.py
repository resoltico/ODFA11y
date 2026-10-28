# SPDX-License-Identifier: MPL-2.0
"""Reviewed outline decisions preserve content and reject stale or ambiguous targets."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from lxml import etree

from odfa11y.adapter import Status
from odfa11y.families.text import HeadingLevel, SetHeadingLevels
from odfa11y.families.text.headings import heading_fingerprint, heading_location
from odfa11y.odf import OdfDocument, Part, qn, select_elements
from odfa11y.plans import load_plan
from odfa11y.remediation.planning import compile_operations
from odfa11y.source_audit import audit_odf
from tests.fixtures.documents import Variant, make_flat, make_package
from tests.fixtures.operations import assert_refused, execute_operations
from tests.fixtures.plans import plan_header, question_for

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

BODY = (
    '<office:text><text:h text:outline-level="1" xml:id="first">'
    "A <text:span>rich</text:span> heading</text:h>"
    '<text:h text:outline-level="4">Details</text:h></office:text>'
)


@pytest.mark.parametrize("make", [make_package, make_flat])
def test_outline_decisions_repair_findings_preserve_words_and_are_idempotent(
    tmp_path: Path, make: Callable[[Path, str, Variant], Path]
) -> None:
    source = make(tmp_path, "text", Variant(body=BODY))
    report = audit_odf(source)
    finding = next(f for f in report.findings if f.rule_id == "HEADING002")
    assert finding.location is not None
    target = finding.location.path
    assert target == "content/heading[2]"
    reviewed_fingerprint = question_for(report, finding).fingerprint
    assert isinstance(reviewed_fingerprint, str)
    operation = SetHeadingLevels({target: HeadingLevel(2, reviewed_fingerprint)})
    once, twice = tmp_path / ("once" + source.suffix), tmp_path / ("twice" + source.suffix)
    execute_operations(source, once, [operation])
    assert "HEADING002" not in {f.rule_id for f in audit_odf(once).findings}
    assert not execute_operations(once, twice, [operation]).changed
    before = OdfDocument.open(source).tree(Part.CONTENT)
    after = OdfDocument.open(twice).tree(Part.CONTENT)
    original = select_elements(before, "//text:h")
    edited = select_elements(after, "//text:h")
    assert ["".join(h.itertext()) for h in original] == ["".join(h.itertext()) for h in edited]
    assert etree.tostring(original[0]) == etree.tostring(edited[0])
    assert edited[1].get(qn("text", "outline-level")) == "2"


def test_all_targets_are_preflighted_before_an_edit(tmp_path: Path) -> None:
    doc = OdfDocument.open(make_package(tmp_path, "text", Variant(body=BODY)))
    headings = select_elements(doc.tree(Part.CONTENT), "//text:h")
    original = etree.tostring(doc.tree(Part.CONTENT))
    operation = SetHeadingLevels({
        "content/heading[id=first]": HeadingLevel(2),
        "content/heading[2]": HeadingLevel(2, "stale"),
    })
    assert all(o.status is Status.FAILED for o in operation.apply(doc))
    assert not doc.dirty
    assert etree.tostring(doc.tree(Part.CONTENT)) == original
    headings[1].text = "Edited after review"
    stale = SetHeadingLevels({"content/heading[2]": HeadingLevel(2, "stale")})
    assert stale.apply(doc)[0].status is Status.FAILED


@pytest.mark.parametrize("level", [0, 11, True, "2", 2.5])
def test_direct_api_rejects_invalid_levels(tmp_path: Path, level: object) -> None:
    doc = OdfDocument.open(make_package(tmp_path, "text", Variant(body=BODY)))
    operation = SetHeadingLevels({"content/heading[id=first]": HeadingLevel(cast("int", level))})
    assert operation.apply(doc)[0].status is Status.FAILED
    assert not doc.dirty


def test_duplicate_xml_identity_and_unreviewed_ordinals_are_rejected(tmp_path: Path) -> None:
    doc = OdfDocument.open(make_package(tmp_path, "text", Variant(body=BODY)))
    assert (
        SetHeadingLevels({"content/heading[2]": HeadingLevel(2)}).apply(doc)[0].status
        is Status.FAILED
    )
    assert not doc.dirty
    headings = select_elements(doc.tree(Part.CONTENT), "//text:h")
    headings[1].set("{http://www.w3.org/XML/1998/namespace}id", "first")
    checkpoint = doc.checkpoint()
    assert (
        SetHeadingLevels({"content/heading[id=first]": HeadingLevel(2)}).apply(doc)[0].status
        is Status.FAILED
    )
    assert not doc.changed_since(checkpoint)


def test_named_identity_is_escaped_and_ordinal_fingerprint_detects_reordering(
    tmp_path: Path,
) -> None:
    doc = OdfDocument.open(make_package(tmp_path, "text", Variant(body=BODY)))
    headings = select_elements(doc.tree(Part.CONTENT), "//text:h")
    headings[0].set("{http://www.w3.org/XML/1998/namespace}id", "section]/heading[2")
    assert heading_location(headings[0], 1).path == "content/heading[id=section%5D%2Fheading%5B2]"
    fingerprint = heading_fingerprint(headings[1])
    parent = headings[1].getparent()
    assert parent is not None
    parent.insert(0, headings[1])
    operation = SetHeadingLevels({"content/heading[2]": HeadingLevel(2, fingerprint)})
    assert operation.apply(doc)[0].status is Status.FAILED


def test_toml_uses_the_exact_report_target(tmp_path: Path) -> None:
    source = make_package(tmp_path, "text", Variant(body=BODY))
    plan = tmp_path / "plan.toml"
    document = OdfDocument.open(source)
    node = select_elements(document.tree(Part.CONTENT), "//text:h")[0]
    reviewed = heading_fingerprint(node)
    plan.write_text(
        plan_header(source)
        + '[decisions."heading.level"."content/heading[id=first]"]\nlevel = 2\nfingerprint = "'
        + reviewed
        + '"\n'
    )
    operations = compile_operations(document, load_plan(plan))
    assert operations == (
        SetHeadingLevels({"content/heading[id=first]": HeadingLevel(2, reviewed)}),
    )
    destination = tmp_path / "out.odt"
    execute_operations(source, destination, operations)
    assert_refused(
        execute_operations(
            source,
            tmp_path / "unreviewed.odt",
            [SetHeadingLevels({"content/heading[2]": HeadingLevel(2)})],
        ),
        match="ordinal heading target requires",
    )


def test_audit_rejects_levels_above_the_supported_range(tmp_path: Path) -> None:
    source = make_package(tmp_path, "text", Variant(body=BODY.replace('level="4"', 'level="11"')))
    assert "HEADING001" in {f.rule_id for f in audit_odf(source).findings}
