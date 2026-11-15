# SPDX-License-Identifier: MPL-2.0
"""Create source-bound production plans from explicit raw fixture answers."""

from collections.abc import Sequence
from pathlib import Path

from odfa11y.errors import PackageError
from odfa11y.odf import OdfDocument
from odfa11y.plans import Plan, PlanHeader, SourceBinding
from odfa11y.plans.fidelity import FidelityPolicy, Pagination
from tests.fixtures.answers import Authored, materialize
lazy from odfa11y.decisions import OpenDecision
lazy from odfa11y.report import Finding, Report


def reviewed_plan(
    source: str | Path, expected: Sequence[Authored] = (), fidelity: FidelityPolicy | None = None
) -> Plan:
    """Bind authored fixture answers using the product's own target domains and answer codec."""
    source = Path(source)
    try:
        document = OdfDocument.open(source)
    except PackageError, OSError:
        document = None
    decisions = materialize(document, expected)
    if source.is_file():
        return Plan.for_source(source, decisions, fidelity=fidelity)
    return Plan(
        PlanHeader(1, SourceBinding("0" * 64), "test"), decisions, fidelity or Pagination.SAME()
    )


def plan_header(source: Path) -> str:
    """Create the binding header for a literal answer fixture.

    Returns
    -------
    str
        A TOML header binding existing input bytes; absent mock inputs use a fixed digest.

    """
    digest = Plan.for_source(source).header.source.sha256 if source.is_file() else "0" * 64
    return f'[plan]\nschema_version = 1\ngenerator = "0.8.0"\nsource.sha256 = "{digest}"\n'


def question_for(report: Report, finding: Finding) -> OpenDecision:
    """Select the unique target question motivating one observed finding.

    Returns
    -------
    OpenDecision
        The actual question, independently matched by rule and diagnostic location.

    """
    [question] = [
        item
        for item in report.decisions
        if finding.rule_id in item.rule_ids
        and item.target is not None
        and finding.location is not None
        and item.target.path == finding.location.path
    ]
    return question
