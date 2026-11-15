# SPDX-License-Identifier: MPL-2.0
"""Reviewed outline decisions preserve content and reject stale or ambiguous targets."""

from typing import cast
lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest
from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.errors import PlanError
from odfa11y.families.text.headings.edit import heading_fingerprint, heading_location
from odfa11y.odf import OdfDocument, Part, qn, select_elements
from odfa11y.plans import parse_tables
from odfa11y.plans.registry import load_plan, registered_kinds
from odfa11y.remediate.compile import compile_decisions
from odfa11y.targets import require_target
from tests.fixtures.answers import (
    apply_in_memory,
    heading_inputs,
    level_answer,
)
from tests.fixtures.documents import Variant, make_flat, make_package
from tests.fixtures.operations import apply_answers
from tests.fixtures.plans import plan_header, question_for

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
    reviewed_fingerprint = require_target(question_for(report, finding).target).fingerprint
    assert isinstance(reviewed_fingerprint, str)
    operation = heading_inputs({target: level_answer(2, reviewed_fingerprint)})
    once, twice = tmp_path / ("once" + source.suffix), tmp_path / ("twice" + source.suffix)
    apply_answers(source, once, [operation])
    assert "HEADING002" not in {f.rule_id for f in audit_odf(once).findings}
    assert not apply_answers(once, twice, [operation]).changed
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
    operation = heading_inputs({
        "content/heading[id=first]": level_answer(2),
        "content/heading[2]": level_answer(2, "0" * 16),
    })
    with pytest.raises(PlanError, match="fingerprint"):
        apply_in_memory(doc, operation)
    assert not doc.dirty
    assert etree.tostring(doc.tree(Part.CONTENT)) == original
    headings[1].text = "Edited after review"
    stale = heading_inputs({"content/heading[2]": level_answer(2, "0" * 16)})
    with pytest.raises(PlanError, match="fingerprint"):
        apply_in_memory(doc, stale)


@pytest.mark.parametrize("level", [0, 11, True, "2", 2.5])
def test_direct_api_rejects_invalid_levels(tmp_path: Path, level: object) -> None:
    doc = OdfDocument.open(make_package(tmp_path, "text", Variant(body=BODY)))
    operation = heading_inputs({"content/heading[id=first]": level_answer(cast("int", level))})
    with pytest.raises(PlanError, match="level"):
        apply_in_memory(doc, operation)
    assert not doc.dirty


def test_duplicate_xml_identity_and_unreviewed_ordinals_are_rejected(tmp_path: Path) -> None:
    doc = OdfDocument.open(make_package(tmp_path, "text", Variant(body=BODY)))
    values = {
        "plan": {"schema_version": 1, "generator": "test", "source": {"sha256": "0" * 64}},
        "decisions": {"heading.level": {"content/heading[2]": {"level": 2}}},
    }
    with pytest.raises(PlanError, match="fingerprint"):
        parse_tables(values, registered_kinds())
    assert not doc.dirty
    headings = select_elements(doc.tree(Part.CONTENT), "//text:h")
    headings[1].set("{http://www.w3.org/XML/1998/namespace}id", "first")
    checkpoint = doc.checkpoint()
    with pytest.raises(PlanError, match="exactly one"):
        apply_in_memory(doc, heading_inputs({"content/heading[id=first]": level_answer(2)}))
    assert not doc.changed_since(checkpoint)


def test_named_identity_is_escaped_and_ordinal_fingerprint_detects_reordering(
    tmp_path: Path,
) -> None:
    doc = OdfDocument.open(make_package(tmp_path, "text", Variant(body=BODY)))
    headings = select_elements(doc.tree(Part.CONTENT), "//text:h")
    headings[0].set("{http://www.w3.org/XML/1998/namespace}id", "section]/heading[2")
    assert heading_location(headings[0], 1).path == "content/heading[id=section%5D%2Fheading%5B2]"
    headings[0].attrib.pop("{http://www.w3.org/XML/1998/namespace}id")
    fingerprint = heading_fingerprint(headings[1])
    parent = headings[1].getparent()
    assert parent is not None
    parent.insert(0, headings[1])
    operation = heading_inputs({"content/heading[2]": level_answer(2, fingerprint)})
    with pytest.raises(PlanError, match="fingerprint"):
        apply_in_memory(doc, operation)


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
    operations = compile_decisions(document, load_plan(plan))
    assert len(operations) == 1
    assert operations[0].kind.id == "heading.level"
    assert operations[0].target is not None
    assert operations[0].target.fingerprint == reviewed
    assert operations[0].answer.level == 2
    destination = tmp_path / "out.odt"
    apply_answers(source, destination, operations)
    plan.write_text(
        plan_header(source) + '[decisions."heading.level"."content/heading[2]"]\nlevel = 2\n'
    )
    with pytest.raises(PlanError, match="fingerprint"):
        load_plan(plan)
    assert not (tmp_path / "unreviewed.odt").exists()


def test_audit_rejects_levels_above_the_supported_range(tmp_path: Path) -> None:
    source = make_package(tmp_path, "text", Variant(body=BODY.replace('level="4"', 'level="11"')))
    assert "HEADING001" in {f.rule_id for f in audit_odf(source).findings}
