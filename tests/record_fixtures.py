# SPDX-License-Identifier: MPL-2.0
"""Construct typed assurance records for evidence publication tests."""

from __future__ import annotations

from dataclasses import replace

from odfa11y.families.text import ADAPTER
from odfa11y.outcomes import StageName, StageStatus
from odfa11y.pdf.fidelity import FidelityPolicy
from odfa11y.pipeline.profiles import PROFILES
from odfa11y.pipeline.record import RunRecord, StageResult
from odfa11y.records import DocumentIdentity
from odfa11y.report import FactKeys, FactSet, Report, rules


def record(*, status: str = "passed", failed_stage: str | None = None) -> RunRecord:
    """Build evidence with real findings, facts and an optional failed gate.

    Returns
    -------
    RunRecord
        A typed pipeline record, ready for publication or review rendering.

    """
    report = Report(kind="pdf", subject="doc.pdf", facts=FactSet({FactKeys.PDF_PAGE_COUNT: 2}))
    report.add(rules.PDF005, "No title display.")
    stages = [
        StageResult(StageName.AUDIT_PDF, StageStatus.PASSED, report=report),
        StageResult(StageName.VALIDATE_PDF, StageStatus.SKIPPED, "not requested"),
    ]
    if status == "failed":
        name = StageName(failed_stage or StageName.REMEDIATE)
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
