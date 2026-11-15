# SPDX-License-Identifier: MPL-2.0
"""Construct typed assurance records for evidence publication tests."""

from dataclasses import replace

from odfa11y.families.text import SPEC
from odfa11y.pdf.audit import PdfMeasurements
from odfa11y.plans.fidelity import Pagination
from odfa11y.progress import Stage
from odfa11y.records import DocumentIdentity
from odfa11y.report import Report
from odfa11y.report.model import ReportKind
from odfa11y.rules import registry as rules
from odfa11y.run.profiles import PROFILES
from odfa11y.run.record import RunRecord, StageResult
from odfa11y.status import StageStatus


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
        StageResult(Stage.AUDIT_PDF, StageStatus.PASSED, report=report),
        StageResult(Stage.VALIDATE_PDF, StageStatus.SKIPPED, "not requested"),
    ]
    if status == "failed":
        name = Stage(failed_stage or Stage.REMEDIATE)
        index = next((i for i, stage in enumerate(stages) if stage.name == name), None)
        if index is None:
            stages.append(StageResult(name, StageStatus.FAILED))
        else:
            stages[index] = replace(stages[index], status=StageStatus.FAILED)
    return RunRecord(
        document=DocumentIdentity("doc.odt", "0" * 64),
        fidelity_policy=Pagination.SAME(),
        profile=PROFILES["verify"],
        stages=stages,
        human_review=SPEC.review_items,
    )
