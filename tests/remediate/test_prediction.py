# SPDX-License-Identifier: AGPL-3.0-only
"""An accepted human answer can leave findings in the unpublished candidate."""

from pathlib import Path

from odfa11y.application.remediate import remediate
from odfa11y.audit import audit_odf
from odfa11y.decisions import Decision, decode_answer
from odfa11y.odf import OdfDocument, Part
from odfa11y.odf import names as xml_names
from odfa11y.plans import Plan
from odfa11y.rules import registry as rules
from tests.fixtures.writer import make_minimal_odt


def test_heading_answer_predicts_remaining_warning_without_writing(tmp_path: Path) -> None:
    original = make_minimal_odt(tmp_path / "original.odt")
    document = OdfDocument.open(original)
    heading = next(document.tree(Part.CONTENT).iter(xml_names.TEXT_H))
    heading.set(xml_names.TEXT_OUTLINE_LEVEL, "3")
    source = tmp_path / "reviewed.odt"
    document.save(source)
    question = next(
        question for question in audit_odf(source).decisions if question.kind.id == "heading.level"
    )
    answer = decode_answer(question.kind.answer_type, {"level": 2}, question.kind.id)
    plan = Plan.for_source(source, [Decision(question.kind, question.target, answer)])
    before = source.read_bytes()
    destination = tmp_path / "candidate.odt"
    result = remediate(source, destination, plan, dry_run=True)
    assert result.exit_status == 0
    assert not result.published
    assert not destination.exists()
    assert source.read_bytes() == before
    (prediction,) = result.predictions
    assert prediction.kind_id == "heading.level"
    assert prediction.resolved == ()
    assert [finding.rule for finding in prediction.remaining] == [rules.HEADING002]
    assert "level 2" in prediction.remaining[0].message
    assert result.candidate is not None
    assert any(finding.rule is rules.HEADING002 for finding in result.candidate.findings)
