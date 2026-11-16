# SPDX-License-Identifier: MPL-2.0
"""Native integration cases for formula semantics."""

lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest

from odfa11y.application.tools import Tools
from odfa11y.native.libreoffice import export_pdfua
from odfa11y.pdf import audit_pdfua
from odfa11y.plans.fidelity import Pagination
from odfa11y.rules import registry as rules
from odfa11y.status import Profile
from tests.families.formula.test_formula_semantics import SOURCE, _plan
from tests.fixtures.native import export_settings, validate_pdfua
from tests.fixtures.operations import apply_answers
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.runs import RunSettings, execute


@pytest.mark.usefixtures("required_verapdf")
def test_native_math_export_retains_the_real_pdf_assurance_failure(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    described = tmp_path / "described.odf"
    apply_answers(SOURCE, described, _plan())
    pdf = export_pdfua(
        described, tmp_path / "formula.pdf", export_settings("math_pdf_Export", soffice)
    )
    report = audit_pdfua(pdf)
    assert report.error_count != 0
    assert rules.PDF005.id in {f.rule_id for f in report.findings}
    assert not validate_pdfua(pdf, executable=verapdf).compliant
    record = execute(
        SOURCE,
        reviewed_plan(SOURCE, _plan(), Pagination.SAME()),
        tmp_path / "evidence",
        RunSettings(tools=Tools(soffice=soffice), profile=Profile.PDF),
    )
    assert record.failed_stage == "audit-pdf", [stage.as_dict() for stage in record.stages]
