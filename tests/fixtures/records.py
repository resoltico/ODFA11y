# SPDX-License-Identifier: MPL-2.0
"""Construct typed assurance records for evidence publication tests."""

from dataclasses import replace

from odfa11y.families.text import ADAPTER
from odfa11y.pdf.fidelity import FidelityPolicy
from odfa11y.progress import Stage
from odfa11y.records import DocumentIdentity
from odfa11y.report import FactKeys, FactSet, Report
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
    report = Report(
        kind=ReportKind.PDF, subject="doc.pdf", facts=FactSet({FactKeys.PDF_PAGE_COUNT: 2})
    )
    report.add(rules.PDF005, "No title display.")
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
        operations=(),
        policy=FidelityPolicy(),
        profile=PROFILES["verify"],
        stages=stages,
        human_review=ADAPTER.review_items,
    )
