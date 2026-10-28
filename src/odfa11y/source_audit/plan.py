# SPDX-License-Identifier: MPL-2.0
"""Prepare source-bound plans from the first-class questions an audit leaves open."""

from __future__ import annotations

import tempfile
from pathlib import Path

from odfa11y.errors import PackageError
from odfa11y.odf import OdfDocument, Use
from odfa11y.plans import Plan, render_plan
from odfa11y.report import Report, rules
from odfa11y.source_capture import capture_source

from .engine import BLOCKING_RULE_IDS, audit_odf


def plan_blockers(report: Report) -> Report | None:
    """Select findings that prevent a safe reviewed plan.

    Returns
    -------
    Report | None
        An independent blocker report, or None when source planning is established.

    """
    findings = [finding for finding in report.findings if finding.rule_id in BLOCKING_RULE_IDS]
    return (
        Report(kind=report.kind, subject=report.subject, findings=findings, sources=report.sources)
        if findings
        else None
    )


def prepare_plan(source: str | Path) -> tuple[Report, str | None]:
    """Audit and print a bound header with disabled typed human answers.

    Returns
    -------
    tuple[Report, str | None]
        The source report and plan template, or no template for blocked inputs.

    """
    source = Path(source)
    try:
        with (
            tempfile.TemporaryDirectory(prefix="odfa11y-plan-") as directory,
            capture_source(source, directory=Path(directory)) as captured,
        ):
            return _prepare_captured(source, captured)
    except (OSError, PackageError) as exc:
        report = Report(kind="odf", subject=str(source), sources=(source,))
        report.add(rules.PKG000, f"Cannot capture source for planning: {exc}")
        return report, None


def _prepare_captured(source: Path, captured: Path) -> tuple[Report, str | None]:
    report = audit_odf(captured)
    report.subject, report.sources = str(source), (source,)
    if plan_blockers(report) is not None:
        return report, None
    document = OdfDocument.open(captured)
    document.require(Use.PLAN)
    header = Plan.for_source(captured).header
    return report, render_plan(header, report.decisions)
