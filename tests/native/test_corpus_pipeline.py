# SPDX-License-Identifier: MPL-2.0
"""Real LibreOffice runs the assurance pipeline on documents Writer itself authored."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odfa11y.content import GraphicAlternative
from odfa11y.evidence import check_bundle
from odfa11y.families.text import LinkifyAddresses, SetGraphicAlternatives
from odfa11y.outcomes import PIPELINE_STAGES
from odfa11y.pdf import validate_pdfua
from odfa11y.pdf.fidelity import FidelityPolicy
from odfa11y.pipeline.context import RunSettings
from odfa11y.pipeline.engine import execute
from odfa11y.remediation import SetMetadata
from odfa11y.tools import Tools
from tests.fixtures.corpus import CORPUS
from tests.fixtures.plans import reviewed_plan

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from odfa11y.adapter import Operation

# Each plan resolves the document's findings that would otherwise fail the audit gate.
PIPELINE_RUNS: dict[str, list[Operation]] = {
    "links.odt": [LinkifyAddresses()],
    "images-undescribed.fodt": [
        SetGraphicAlternatives({"Image1": GraphicAlternative("Red square")})
    ],
    "header-footer.fodt": [],
}


@pytest.mark.integration
@pytest.mark.parametrize("name", PIPELINE_RUNS)
def test_the_pipeline_records_a_writer_run_and_rejects_invalid_link_exports(
    name: str, tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    plan = [SetMetadata(title="Corpus document", language="en-US"), *PIPELINE_RUNS[name]]
    record = execute(
        CORPUS / name,
        reviewed_plan(CORPUS / name, plan, FidelityPolicy()),
        tmp_path / "out",
        RunSettings(tools=Tools(soffice=soffice)),
    )
    stages = {stage.name.value: stage.status for stage in record.stages}
    assert tuple(stages) == PIPELINE_STAGES
    diagnostics = [stage.as_dict() for stage in record.stages]
    assert stages["export-remediated"] == "passed", diagnostics
    pdf_stage = next(stage for stage in record.stages if stage.name == "audit-pdf")
    assert pdf_stage.report is not None
    pdf_rules = {finding.rule_id for finding in pdf_stage.report.findings}
    if name == "links.odt":
        result = validate_pdfua(
            tmp_path / "out" / "remediated.pdf", executable=external_tool("verapdf")
        )
        failures = {(failure.clause, failure.test_number) for failure in result.failures}
        assert failures == {("7.18.1", "2"), ("7.18.5", "2")}, failures
        assert pdf_rules == {"PDF019"}, diagnostics
        assert record.failed_stage == "audit-pdf", diagnostics
        assert record.exit_status == 2
        assert stages["fidelity"] == "skipped", diagnostics
    else:
        assert record.passed, diagnostics
        assert stages["fidelity"] == "passed", diagnostics
    assert check_bundle(tmp_path / "out") == []
