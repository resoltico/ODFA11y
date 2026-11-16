# SPDX-License-Identifier: MPL-2.0
"""Prepare source-bound plans from the first-class questions an audit leaves open."""

import tempfile
from pathlib import Path

from odfa11y.audit.engine import BLOCKING_RULES, audit_document
from odfa11y.audit.questions import available_questions, with_context
from odfa11y.capture import CapturedSource, capture_source
from odfa11y.decisions import Decision, OpenDecision
from odfa11y.errors import PackageError
from odfa11y.odf import OdfDocument, Use
from odfa11y.plans import Plan, render_plan
from odfa11y.report import Report
from odfa11y.report.model import ReportKind
from odfa11y.rules import registry as rules


def plan_blockers(report: Report) -> Report | None:
    """Select findings that prevent a safe reviewed plan.

    Returns
    -------
    Report | None
        An independent blocker report, or None when source planning is established.

    """
    findings = [finding for finding in report.findings if finding.rule in BLOCKING_RULES]
    return (
        Report(kind=report.kind, subject=report.subject, findings=findings, _sources=report.sources)
        if findings
        else None
    )


def prepare_plan(
    source: str | Path, *, previous: Plan | None = None, include_all: bool = False
) -> tuple[Report, str | None]:
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
            return _prepare_captured(source, captured, previous=previous, include_all=include_all)
    except (OSError, PackageError) as exc:
        report = Report(kind=ReportKind.ODF, subject=str(source), _sources=(source,))
        report.raise_(rules.PKG001, f"Cannot capture source for planning: {exc}")
        return report, None


def _prepare_captured(
    source: Path, captured: CapturedSource, *, previous: Plan | None, include_all: bool
) -> tuple[Report, str | None]:
    document = OdfDocument.open(captured.path)
    report = audit_document(document, subject=str(source), source=source)
    report.subject, report.sources = str(source), (source,)
    if plan_blockers(report) is not None:
        return report, None
    document.require(Use.PLAN)
    header = Plan.for_source(captured).header
    available = available_questions(document)
    questions = tuple(with_context(question, available) for question in report.decisions)
    carried, not_carried = _carry(previous, available)
    raised = {_key(question) for question in questions}
    carried_keys = {_key(answer) for answer in carried}
    optional = tuple(
        question
        for question in available
        if _key(question) not in raised and (include_all or _key(question) in carried_keys)
    )
    return report, render_plan(
        header,
        questions,
        findings=report.findings,
        optional=optional,
        answers=carried,
        not_carried=not_carried,
        fidelity=previous.fidelity if previous else None,
    )


def _key(decision: Decision | OpenDecision) -> tuple[str, str | None]:
    return decision.kind.id, decision.target.path if decision.target else None


def _carry(
    previous: Plan | None, available: tuple[OpenDecision, ...]
) -> tuple[tuple[Decision, ...], tuple[tuple[Decision, str], ...]]:
    if previous is None:
        return (), ()
    current = {_key(question): question for question in available}
    carried = []
    not_carried = []
    for answer in previous.decisions:
        match = current.get(_key(answer))
        if match is None:
            not_carried.append((
                answer,
                "The decision kind or target is unavailable in this source.",
            ))
        elif match.target != answer.target:
            not_carried.append((answer, "The target fingerprint changed; review a fresh answer."))
        else:
            carried.append(answer)
    return tuple(carried), tuple(not_carried)
