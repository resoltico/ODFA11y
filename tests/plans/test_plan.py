# SPDX-License-Identifier: MPL-2.0
"""Bound plan files validate registered answers and compile in dependency order."""

from pathlib import Path

import pytest

from odfa11y.decisions import Decision, OpenDecision
from odfa11y.decisions.answers import DocumentMetadataAnswer
from odfa11y.decisions.decision import QuestionContext
from odfa11y.errors import IoFailure, PlanError
from odfa11y.odf import OdfDocument
from odfa11y.plans import Plan, PlanHeader, SourceBinding, render_plan
from odfa11y.plans.fidelity import Pagination
from odfa11y.plans.registry import load_plan, registered_kinds
from odfa11y.remediate.compile import compile_decisions
from tests.fixtures.paths import REPOSITORY
from tests.fixtures.schema import assert_record_schema
from tests.fixtures.writer import make_minimal_odt
lazy from odfa11y.decisions.edit import Status

HEADER = '[plan]\nschema_version = 1\ngenerator = "0.8.0"\nsource.sha256 = "' + "a" * 64 + '"\n'
FULL = (
    HEADER
    + """
[decisions."text.remove_spacers"]
enabled = true
[decisions."document.metadata"]
title = "Decision"
description = "Decision letter"
language = "en-GB"
[decisions."document.odf_version"]
version = "1.3"
[decisions."text.linkify_addresses"]
enabled = true
[decisions."table.headers"."content/table[name=Data]"]
rows = 1
fingerprint = "0123456789abcdef"
[decisions."graphic.alternative"."content/frame[name=Logo]"]
title = "Organisation"
description = "Organisation logo."
fingerprint = "fedcba9876543210"
[decisions."text.spacing"]
reference_text = "Reference"
target_styles = ["BodyTight"]
exact_reference = true
[fidelity]
pagination = "may-change"
"""
)


def write(tmp_path: Path, text: str) -> Path:
    """Write a plan fixture.

    Returns
    -------
    Path
        The persisted review file.

    """
    path = tmp_path / "review.plan.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_full_plan_compiles_in_canonical_order(tmp_path: Path) -> None:
    plan = load_plan(write(tmp_path, FULL))
    assert_record_schema(plan)
    document = OdfDocument.open(
        make_minimal_odt(
            tmp_path / "source.odt",
            features={"with_image_without_alt": True, "with_data_table": True},
        )
    )
    plan = Plan(
        plan.header,
        tuple(
            Decision(
                item.kind,
                item.kind.domain.binding(document, item.target.path)
                if item.target is not None and item.kind.domain is not None
                else None,
                item.answer,
            )
            for item in plan.decisions
        ),
        plan.fidelity,
    )
    operations = compile_decisions(document, plan)
    assert [item.kind.id for item in operations] == [
        "document.odf_version",
        "document.metadata",
        "text.linkify_addresses",
        "text.remove_spacers",
        "graphic.alternative",
        "table.headers",
        "text.spacing",
    ]
    assert operations[1].answer == DocumentMetadataAnswer("Decision", "Decision letter", "en-GB")
    assert plan.fidelity == Pagination.MAY_CHANGE


def test_header_only_plan_requests_nothing(tmp_path: Path) -> None:
    plan = load_plan(write(tmp_path, HEADER))
    assert plan.decisions == ()
    assert plan.fidelity == Pagination.SAME()


def test_false_switches_remain_validated_decisions_and_disable_their_edits(tmp_path: Path) -> None:
    plan = load_plan(
        write(
            tmp_path,
            HEADER
            + """
[decisions."text.linkify_addresses"]
enabled = false
[decisions."text.remove_spacers"]
enabled = false
""",
        )
    )
    document = OdfDocument.open(make_minimal_odt(tmp_path / "source.odt"))
    decisions = compile_decisions(document, plan)
    assert len(decisions) == 2
    for decision in decisions:
        assert decision.answer.enabled is False
        outcomes = decision.kind.edit(document, decision)
        assert all(outcome.status is Status.UNCHANGED for outcome in outcomes)
    assert not document.dirty


@pytest.mark.parametrize(
    "content",
    [
        '[decisions."document.metadata"]\ntitel = "Typo"',
        '[decisions."document.metadata"]\nlanguage = 7',
        '[decisions."document.odf_version"]\nversion = "1.2"',
        '[decisions."text.linkify_addresses"]\nenabled = "false"',
        '[decisions."table.headers"]\n"content/table[1]" = true',
        '[decisions."table.headers"]\n"content/table[1]" = 0',
        '[decisions."table.headers"."content/table[1]"]\nrows = 1\nextra = 1',
        '[decisions]\n"text.spacing" = 1',
        '[decisions."missing.kind"]',
        '[decisions."graphic.alternative"."content/frame[1]"]\ndescription = 7',
        '[decisions."graphic.alternative"."content/frame[1]"]\ndescripton = "Typo"',
        'document = "invalid"',
        "[unknown]",
        "[unrecognised_family]",
        "[remediation]",
        "[alt_text]",
        '[decisions."text.spacing"]\nreference_text = "x"',
        '[decisions."text.spacing"]\ntarget_styles = ["A"]',
        '[decisions."text.spacing"]\nreference_text = "x"\ntarget_styles = ["A"]\nexact = true',
        '[fidelity]\npagination = "never"',
        "[fidelity]\nraster_tolerance = -1",
        "[fidelity]\nink_threshold = 300",
        "[fidelity]\ndpi = 0",
        "not = valid = toml",
    ],
)
def test_invalid_plan_is_rejected(tmp_path: Path, content: str) -> None:
    with pytest.raises(PlanError):
        load_plan(write(tmp_path, HEADER + content))


def test_missing_plan_file_is_an_io_failure(tmp_path: Path) -> None:
    with pytest.raises(IoFailure, match="FileNotFoundError"):
        load_plan(tmp_path / "absent.toml")


def test_example_plan_is_valid(tmp_path: Path) -> None:
    guide = (REPOSITORY / "docs/PLAN.md").read_text(encoding="utf-8")
    example = guide.split("```toml\n", 1)[1].split("\n```", 1)[0]
    plan = load_plan(write(tmp_path, example))
    assert plan.decisions[0].answer.title == "Example report"


@pytest.mark.parametrize("tag", ["en-u", "en-a-foo-a-bar", "sl-rozaj-rozaj"])
def test_plan_rejects_malformed_language_syntax(tmp_path: Path, tag: str) -> None:
    path = write(tmp_path, HEADER + f'[decisions."document.metadata"]\nlanguage = "{tag}"\n')
    with pytest.raises(PlanError, match="Invalid language"):
        load_plan(path)


def test_unanswered_blocks_are_inert_but_typoes_and_partial_answers_are_rejected(
    tmp_path: Path,
) -> None:
    plan = load_plan(
        write(
            tmp_path,
            HEADER
            + '\n[decisions."document.metadata"]\n'
            + '[decisions."graphic.alternative"."content/frame[1]"]\nfingerprint = "stale"\n',
        )
    )
    assert plan.decisions == ()
    assert [(block.kind_id, block.fingerprint) for block in plan.unanswered] == [
        ("document.metadata", None),
        ("graphic.alternative", "stale"),
    ]
    assert plan.as_dict()["decisions"] == {
        "document.metadata": {},
        "graphic.alternative": {"content/frame[1]": {"fingerprint": "stale"}},
    }
    for answer in ('description = ""', 'description = "Accessible"', 'descripton = "Typo"'):
        with pytest.raises(PlanError):
            load_plan(
                write(
                    tmp_path,
                    HEADER
                    + '\n[decisions."graphic.alternative"."content/frame[1]"]\n'
                    + 'fingerprint = "stale"\n'
                    + answer,
                )
            )


def test_question_context_redacts_before_shortening_and_escaping() -> None:

    question = OpenDecision(
        registered_kinds()["text.linkify_addresses"],
        None,
        {},
        context=QuestionContext(
            "paragraph", "/home/" + "private-person" * 10 + "/chart.png\n\u202e"
        ),
    )
    template = render_plan(PlanHeader(1, SourceBinding("0" * 64), "test"), (), optional=[question])
    assert "private-person" not in template
    assert "<path>/chart.png" in template
    assert "\u202e" not in template
    assert r"\u202e" in template
    assert r"\n" in template


def test_unraised_questions_are_refused_outside_the_optional_override_section() -> None:
    question = OpenDecision(registered_kinds()["text.linkify_addresses"], None, {})
    with pytest.raises(PlanError, match="optional overrides"):
        render_plan(PlanHeader(1, SourceBinding("0" * 64), "test"), [question])
