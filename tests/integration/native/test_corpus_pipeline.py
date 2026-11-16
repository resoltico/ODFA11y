# SPDX-License-Identifier: MPL-2.0
"""Real LibreOffice runs the assurance pipeline on documents Writer itself authored."""

lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest

from odfa11y.application.tools import Tools
from odfa11y.evidence import check_bundle
from odfa11y.plans.fidelity import Pagination
from odfa11y.rules import registry as rules
from tests.fixtures.answers import (
    Authored,
    address_input,
    graphic_answer,
    graphic_inputs,
    metadata_input,
)
from tests.fixtures.corpus import CORPUS
from tests.fixtures.native import validate_pdfua
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.runs import STAGE_NAMES, RunSettings, execute

# Each plan resolves the document's findings that would otherwise fail the audit gate.
PIPELINE_RUNS: dict[str, list[Authored]] = {
    "links.odt": [address_input()],
    "images-undescribed.fodt": [graphic_inputs({"Image1": graphic_answer("Red square")})],
    "header-footer.fodt": [],
}


@pytest.mark.parametrize("name", PIPELINE_RUNS)
def test_the_pipeline_records_a_writer_run_and_rejects_invalid_link_exports(
    name: str, tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    plan = [metadata_input(title="Corpus document", language="en-US"), *PIPELINE_RUNS[name]]
    record = execute(
        CORPUS / name,
        reviewed_plan(CORPUS / name, plan, Pagination.SAME()),
        tmp_path / "out",
        RunSettings(tools=Tools(soffice=soffice)),
    )
    stages = {stage.name.value: stage.outcome.status for stage in record.stages}
    assert tuple(stages) == STAGE_NAMES
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
        assert pdf_rules == {rules.PDF020.id}, diagnostics
        assert record.failed_stage == "audit-pdf", diagnostics
        assert record.exit_status == 2
        assert stages["fidelity"] == "skipped", diagnostics
    else:
        assert record.passed, diagnostics
        assert stages["fidelity"] == "passed", diagnostics
    assert check_bundle(tmp_path / "out") == []
