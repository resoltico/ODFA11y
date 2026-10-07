# SPDX-License-Identifier: MPL-2.0
"""Native mathematics remains unchanged while alternatives/language are edited explicitly."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

import pytest

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.audit import audit_odf
from odfa11y.config import load_config
from odfa11y.errors import ConfigError, RemediationError
from odfa11y.families import adapter_for
from odfa11y.families.formula import SetFormulaAlternative
from odfa11y.families.formula.expression import fingerprint
from odfa11y.fidelity import FidelityPolicy
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.pdf import ExportSettings, audit_pdfua, export_pdfua, validate_pdfua
from odfa11y.pipeline import PipelineOptions, run_pipeline
from odfa11y.remediation import SetMetadata, remediate

from .documents import Variant, make_flat

if TYPE_CHECKING:
    from collections.abc import Callable

SOURCE = Path(__file__).parent / "family_corpus/sum-formula.odf"


@dataclass(frozen=True, slots=True)
class ChangeMathematics(Operation):
    """Negative control: change a symbol, leaving an unchanged StarMath annotation."""

    name: ClassVar[str] = "change_mathematics"

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        symbol = select_elements(document.edit(Part.CONTENT), "//math:mi")[0]
        symbol.text = "z"
        return (Outcome(self.name, Status.APPLIED, "Changed a symbol", count=1),)


def _plan() -> list[Operation]:
    root = OdfDocument.open(SOURCE).tree(Part.CONTENT).getroot()
    return [
        SetMetadata(language="en-US"),
        SetFormulaAlternative("a plus b equals c", fingerprint(root)),
    ]


def test_native_formula_validates_and_missing_alternative_has_a_reviewed_target() -> None:
    document = OdfDocument.open(SOURCE)
    result = validate(document)
    assert result.available
    assert result.version == "1.4"
    assert result.count == 0
    report = audit_odf(SOURCE, schema=True)
    finding = next(f for f in report.findings if f.rule_id == "MATH002")
    assert finding.remedy == "formula.alternative"
    assert finding.location is not None
    assert finding.location.path == "content/formula"
    assert finding.details["fingerprint"] == fingerprint(document.tree(Part.CONTENT).getroot())


def test_explicit_alternative_keeps_the_expression_and_native_annotation_and_is_idempotent(
    tmp_path: Path,
) -> None:
    before = OdfDocument.open(SOURCE)
    adapter = adapter_for(before.kind)
    once, twice = tmp_path / "once.odf", tmp_path / "twice.odf"
    assert remediate(SOURCE, once, _plan()).changed
    assert not remediate(once, twice, _plan()).changed
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
    with pytest.raises(RemediationError, match="content changed"):
        remediate(SOURCE, destination, [ChangeMathematics()])
    assert not destination.exists()


def test_stale_formula_decision_is_rejected_without_edits() -> None:
    document = OdfDocument.open(SOURCE)
    outcome = SetFormulaAlternative("A chosen alternative", "stale").apply(document)[0]
    assert outcome.status is Status.FAILED
    assert document.edit_count == 0


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
    plan.write_text('[formula]\nalternative = "a plus b equals c"\nfingerprint = "reviewed"\n')
    assert load_config(plan).operations == (SetFormulaAlternative("a plus b equals c", "reviewed"),)
    plan.write_text('[formula]\nfingerprint = "reviewed"\n')
    with pytest.raises(ConfigError, match="nonblank spoken alternative"):
        load_config(plan)


@pytest.mark.integration
def test_native_math_export_retains_the_real_pdf_assurance_failure(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    described = tmp_path / "described.odf"
    remediate(SOURCE, described, _plan())
    pdf = export_pdfua(
        described, tmp_path / "formula.pdf", ExportSettings("math_pdf_Export", soffice)
    )
    report = audit_pdfua(pdf)
    assert not report.passed
    assert "PDF004" in {f.rule_id for f in report.findings}
    assert not validate_pdfua(pdf, executable=verapdf).compliant
    record = run_pipeline(
        SOURCE,
        _plan(),
        FidelityPolicy(),
        tmp_path / "evidence",
        PipelineOptions(profile="verify", soffice=soffice),
    )
    assert record.failed_stage == "audit-pdf", [stage.as_dict() for stage in record.stages]
