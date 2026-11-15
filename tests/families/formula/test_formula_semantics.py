# SPDX-License-Identifier: MPL-2.0
"""Native mathematics remains unchanged while alternatives/language are edited explicitly."""

from dataclasses import dataclass
from typing import ClassVar, override
lazy from pathlib import Path

import pytest

from odfa11y.audit import audit_odf
from odfa11y.concepts.edits import Operation, Outcome, Status
from odfa11y.errors import PlanError
from odfa11y.families import adapter_for
from odfa11y.families.formula import SetFormulaAlternative
from odfa11y.families.formula.expression import fingerprint
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.plans import load_plan
from odfa11y.remediate import SetMetadata
from odfa11y.remediate.compile import compile_operations
from tests.fixtures.documents import Variant, make_flat
from tests.fixtures.operations import assert_refused, execute_operations
from tests.fixtures.paths import TESTS
from tests.fixtures.plans import plan_header

SOURCE = TESTS / "family_corpus/sum-formula.odf"


@dataclass(frozen=True, slots=True)
class ChangeMathematics(Operation):
    """Negative control: change a symbol, leaving an unchanged StarMath annotation."""

    name: ClassVar[str] = "change_mathematics"

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        symbol = select_elements(document.tree(Part.CONTENT), "//math:mi")[0]
        symbol.text = "z"
        return (Outcome(self.name, Status.APPLIED, "Changed a symbol", count=1),)


def _plan() -> list[Operation]:
    root = OdfDocument.open(SOURCE).tree(Part.CONTENT).getroot()
    return [
        SetMetadata(language="en-US"),
        SetFormulaAlternative("a plus b equals c", fingerprint(root)),
    ]


def test_native_formula_validates_and_missing_alternative_requests_an_answer() -> None:
    document = OdfDocument.open(SOURCE)
    result = validate(document)
    assert result.available
    assert result.version == "1.4"
    assert result.count == 0
    report = audit_odf(SOURCE, schema=True)
    finding = next(f for f in report.findings if f.rule_id == "MATH002")
    question = next(d for d in report.decisions if d.kind.id == "formula.alternative")
    assert question.target is not None
    assert question.target.path == "content/formula"
    assert question.target.fingerprint == fingerprint(document.tree(Part.CONTENT).getroot())
    assert finding.location is not None
    assert finding.location.path == "content/formula"
    assert "MATH002" in question.rule_ids


def test_explicit_alternative_keeps_the_expression_and_native_annotation_and_is_idempotent(
    tmp_path: Path,
) -> None:
    before = OdfDocument.open(SOURCE)
    adapter = adapter_for(before.kind)
    once, twice = tmp_path / "once.odf", tmp_path / "twice.odf"
    assert execute_operations(SOURCE, once, _plan()).changed
    assert not execute_operations(once, twice, _plan()).changed
    after = OdfDocument.open(twice)
    assert adapter.snapshot(before) == adapter.snapshot(after)
    root = after.tree(Part.CONTENT).getroot()
    assert root.get("alttext") == "a plus b equals c"
    assert root.get("{http://www.w3.org/XML/1998/namespace}lang") == "en-US"
    assert select_elements(root, ".//math:annotation")[0].text == "a + b = c"
    assert validate(after).count == 0
    assert "MATH002" not in {f.rule_id for f in audit_odf(twice).findings}
    assert once.read_bytes() == twice.read_bytes()


def test_mathematical_changes_are_rejected_before_publication(tmp_path: Path) -> None:
    destination = tmp_path / "wrong.odf"
    assert_refused(
        execute_operations(SOURCE, destination, [ChangeMathematics()]), match="content changed"
    )
    assert not destination.exists()


def test_stale_formula_decision_is_rejected_without_edits() -> None:
    document = OdfDocument.open(SOURCE)
    outcome = SetFormulaAlternative("A chosen alternative", "stale").apply(document)[0]
    assert outcome.status is Status.FAILED
    assert not document.dirty


def test_mathml_schema_rejects_invalid_expression_content() -> None:
    document = OdfDocument.open(SOURCE)
    root = document.tree(Part.CONTENT).getroot()
    select_elements(root, ".//math:mrow")[0].tag = qn("math", "not-math")
    result = validate(document)
    assert result.available
    assert result.count > 0
    assert any(
        "not-math" in message for messages in result.messages().values() for message in messages
    )


def test_flat_office_formula_wrapper_is_rejected_as_an_unsupported_representation(
    tmp_path: Path,
) -> None:
    source = make_flat(
        tmp_path, "text", Variant(media_type="application/vnd.oasis.opendocument.formula")
    )
    assert "MATH001" in {f.rule_id for f in audit_odf(source).findings}
    document = OdfDocument.open(source)
    assert SetFormulaAlternative("A formula").apply(document)[0].status is Status.FAILED


def test_formula_configuration_is_explicit_and_strict(tmp_path: Path) -> None:
    plan = tmp_path / "plan.toml"
    digest = fingerprint(OdfDocument.open(SOURCE).tree(Part.CONTENT).getroot())
    table = '[decisions."formula.alternative"."content/formula"]\n'
    plan.write_text(
        plan_header(SOURCE)
        + table
        + f'fingerprint = "{digest}"\n'
        + 'alternative = "a plus b equals c"\n'
    )
    assert compile_operations(OdfDocument.open(SOURCE), load_plan(plan)) == (
        SetFormulaAlternative("a plus b equals c", digest),
    )
    plan.write_text(plan_header(SOURCE) + table)
    assert load_plan(plan).decisions == ()
    for answer in (
        'alternative = ""',
        'alternative = "a"\nfingerprint = "reviewed"',
        'alternative = "a"',
    ):
        plan.write_text(plan_header(SOURCE) + table + answer)
        with pytest.raises(PlanError):
            load_plan(plan)
    plan.write_text(plan_header(SOURCE) + '[decisions."formula.alternative"]\nalternative = "a"')
    with pytest.raises(PlanError):
        load_plan(plan)
