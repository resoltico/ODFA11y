# SPDX-License-Identifier: MPL-2.0
"""Construct typed assurance records for evidence publication tests."""

from dataclasses import replace

from odfa11y.batch.record import BatchItemResult
from odfa11y.errors import DocumentRefusal, PlanError, ToolFailure
from odfa11y.families.text import SPEC
from odfa11y.pdf.audit import PdfMeasurements
from odfa11y.plans.fidelity import Pagination
from odfa11y.progress import Stage
from odfa11y.report import Report
from odfa11y.report.model import ReportKind
from odfa11y.rules import registry as rules
from odfa11y.run.record import DocumentIdentity, RunRecord, StageResult
from odfa11y.status import GateFailed, Passed, Profile, Refused, Skipped, SkipReason


def record(*, status: str = "passed", failed_stage: str | None = None) -> RunRecord:
    """Build evidence with real findings, facts and an optional failed gate.

    Returns
    -------
    RunRecord
        A typed pipeline record, ready for publication or review rendering.

    """
    report = Report[object](
        kind=ReportKind.PDF, subject="doc.pdf", facts=(PdfMeasurements(page_count=2),)
    )
    report.raise_(rules.PDF006, "No title display.")
    stages = [
        StageResult(Stage.AUDIT_PDF, Passed(report)),
        StageResult(Stage.VALIDATE_PDF, Skipped(SkipReason.PROFILE)),
    ]
    if status == "failed":
        name = Stage(failed_stage or Stage.REMEDIATE)
        index = next((i for i, stage in enumerate(stages) if stage.name == name), None)
        if index is None:
            stages.append(StageResult(name, Refused(DocumentRefusal("Controlled refusal"))))
        else:
            stages[index] = replace(
                stages[index], outcome=Refused(DocumentRefusal("Controlled refusal"))
            )
    return RunRecord(
        document=DocumentIdentity("doc.odt", "0" * 64),
        fidelity_policy=Pagination.SAME(),
        profile=Profile.PDF,
        stages=tuple(stages),
        human_review=SPEC.review_items,
    )


def batch_item(identity: str, status: int):
    """Build aggregate inputs from actual report gates and typed preparation failures."""

    if status in (3, 4):
        error = (
            ToolFailure("Controlled execution failure")
            if status == 3
            else PlanError("Controlled plan failure")
        )
        return BatchItemResult(identity, error.as_record(), _started=True)
    result = record()
    report = Report(kind=ReportKind.ODF, subject="fixture.odt")
    if status == 1:
        report.raise_(rules.LINK001)
    elif status == 2:
        report.raise_(rules.PKG001)
    outcome = GateFailed(report) if status else Passed(report)
    result = replace(
        result, profile=Profile.PRODUCTION, stages=(StageResult(Stage.AUDIT_REMEDIATED, outcome),)
    )
    return BatchItemResult(identity, result, _started=True)
