# SPDX-License-Identifier: MPL-2.0
"""New source-bound plans carry only answers whose reviewed identities survive."""

import tomllib
from pathlib import Path

import pytest

import odfa11y as api
from odfa11y.application.remediate import remediate
from odfa11y.audit import audit_odf, prepare_plan
from odfa11y.decisions import Decision, decode_answer
from odfa11y.errors import PlanError
from odfa11y.odf import OdfDocument, Part
from odfa11y.odf import names as xml_names
from odfa11y.plans import Plan, parse_tables
from odfa11y.plans.fidelity import Pagination
from odfa11y.plans.model import UnansweredDecision
from odfa11y.plans.registry import registered_kinds
from tests.fixtures.writer import make_minimal_odt


def test_new_plan_carries_matching_answers_and_fidelity_but_comments_changed_targets(
    tmp_path: Path,
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt", features={"with_image_without_alt": True})
    question = next(
        question
        for question in audit_odf(source).decisions
        if question.kind.id == "graphic.alternative"
    )
    answer = Decision(
        question.kind,
        question.target,
        decode_answer(question.kind.answer_type, {"title": "Reviewed logo"}, question.kind.id),
    )
    previous = Plan.for_source(source, [answer], fidelity=Pagination.MAY_CHANGE)
    document = OdfDocument.open(source)
    title = next(document.tree(Part.META).iter(xml_names.DC_TITLE))
    title.text = "Changed unrelated metadata"
    changed = tmp_path / "changed.odt"
    document.save(changed)
    _, template = prepare_plan(changed, previous=previous)
    assert template is not None
    plan = parse_tables(tomllib.loads(template), registered_kinds())
    assert plan.header.source != previous.header.source
    assert plan.decisions == previous.decisions
    assert plan.fidelity == previous.fidelity
    plan.verify_source(changed)
    frame = next(document.tree(Part.CONTENT).iter(xml_names.DRAW_FRAME))
    frame.set(xml_names.SVG_WIDTH, "5cm")
    different = tmp_path / "different.odt"
    document.save(different)
    _, template = prepare_plan(different, previous=previous)
    assert template is not None
    assert "# Not carried:" in template
    assert '# title = "Reviewed logo"' in template
    plan = parse_tables(tomllib.loads(template), registered_kinds())
    assert plan.decisions == ()
    assert plan.fidelity == previous.fidelity
    assert plan.unanswered


def test_optional_language_overrides_are_available_only_when_requested(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    report, default = prepare_plan(source)
    _, optional = prepare_plan(source, include_all=True)
    assert default is not None
    assert optional is not None
    assert not [question for question in report.decisions if question.kind.id == "language.target"]
    assert 'decisions."language.target"' not in default
    assert "# Optional overrides (no finding raised)" in optional
    assert 'decisions."language.target"' in optional
    plan = parse_tables(tomllib.loads(optional), registered_kinds())
    assert plan.decisions == ()
    assert any(block.kind_id == "language.target" for block in plan.unanswered)


@pytest.mark.parametrize("target_state", ["fingerprint", "missing"])
def test_stale_unanswered_block_warns_without_changing_or_failing_a_dry_run(
    tmp_path: Path, target_state: str
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt", features={"with_image_without_alt": True})
    _, template = prepare_plan(source)
    assert template is not None
    values = tomllib.loads(template)
    values["decisions"]["graphic.alternative"]["content/frame[name=Logo]"]["fingerprint"] = "stale"
    if target_state == "missing":
        values["decisions"]["graphic.alternative"] = {
            "content/frame[name=Absent]": {"fingerprint": "0" * 16}
        }
    plan = parse_tables(values, registered_kinds())
    before = source.read_bytes()
    destination = tmp_path / "out.odt"
    result = remediate(source, destination, plan, dry_run=True)
    (block,) = result.unanswered
    assert block.stale
    assert block.reason
    assert ("fingerprint" if target_state == "fingerprint" else "exactly one") in block.reason
    assert result.outcomes == ()
    assert result.exit_status == 0
    assert not destination.exists()
    assert source.read_bytes() == before


def test_loading_reports_invalid_answers_and_every_independent_source_binding(
    tmp_path: Path,
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt", features={"with_image_without_alt": True})
    original = source.read_bytes()
    document = OdfDocument.open(source)
    header = Plan.for_source(source).header
    (question,) = [
        question
        for question in audit_odf(source).decisions
        if question.kind.id == "graphic.alternative"
    ]
    assert question.target is not None
    actual = question.target.fingerprint
    wrong = ("0" if actual[0] != "0" else "1") + actual[1:]
    digest = header.source.sha256
    wrong_digest = ("0" if digest[0] != "0" else "1") + digest[1:]
    plan_file = tmp_path / "invalid.toml"
    plan_file.write_text(
        '[plan]\nschema_version = 1\ngenerator = "test"\nsource.sha256 = "' + wrong_digest + '"\n'
        '[decisions."graphic.alternative"."content/frame[name=Logo]"]\n'
        'title = " "\nfingerprint = "' + wrong + '"\n'
        '[decisions."graphic.alternative"."content/frame[name=Absent]"]\n'
        'description = 7\nfingerprint = "' + wrong + '"\n'
        '[decisions."document.metadata"]\ntitel = "typo"\nlanguage = 7\n'
        '[decisions."unknown.kind"]\n'
    )
    destination = tmp_path / "output.odt"
    with pytest.raises(PlanError) as raised:
        api.remediate(source, destination, plan_file)
    text = str(raised.value)
    for expected in (
        "title",
        "non-blank",
        "description",
        "titel",
        "language",
        "unknown.kind",
        "fingerprint mismatch",
        "exactly one",
        "digest mismatch",
    ):
        assert expected in text
    assert source.read_bytes() == original
    assert not destination.exists()
    assert document.dirty == frozenset()


def test_answer_fields_select_the_answered_contract_when_fingerprint_is_missing(
    tmp_path: Path,
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    values = {
        "plan": Plan.for_source(source).as_dict()["plan"],
        "decisions": {"graphic.alternative": {"content/frame[1]": {"title": " "}}},
    }
    with pytest.raises(PlanError) as raised:
        parse_tables(values, registered_kinds())
    assert any(
        "fingerprint" in problem and "required" in problem for problem in raised.value.problems
    )
    assert any("title" in problem and "non-blank" in problem for problem in raised.value.problems)


def test_an_answer_and_unanswered_block_cannot_silently_overwrite_each_other(
    tmp_path: Path,
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    kind = registered_kinds()["document.metadata"]
    answer = Decision(kind, None, decode_answer(kind.answer_type, {"title": "Reviewed"}, kind.id))
    header = Plan.for_source(source).header
    with pytest.raises(PlanError, match="same decision kind"):
        Plan(header, (answer,), unanswered=(UnansweredDecision(kind, None),))
