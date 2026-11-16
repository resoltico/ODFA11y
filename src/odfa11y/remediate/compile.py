# SPDX-License-Identifier: AGPL-3.0-only
"""Validate canonical bindings and order registered decisions for direct execution."""

from odfa11y.decisions import Decision
from odfa11y.errors import PlanError, Remedy, RemedyAction
from odfa11y.families import require_spec
from odfa11y.odf import OdfDocument
from odfa11y.plans import Plan
from odfa11y.remediate.catalogue import registered_kinds
from odfa11y.remediate.document_ops import COMMON_KINDS


def compile_decisions(
    document: OdfDocument, plan: Plan, *, source_sha256: str | None = None
) -> tuple[Decision, ...]:
    """Check every answered binding before any edit and sort by registered dependency order."""
    kinds = registered_kinds()
    applicable = (*COMMON_KINDS, *require_spec(document.kind).kinds)
    positions = {kind.id: index for index, kind in enumerate(applicable)}
    problems = []
    if source_sha256 is not None and plan.header.source.sha256 != source_sha256:
        problems.append("Plan/source digest mismatch; create a newly bound plan with plan --from.")
    indices = {}
    for decision in plan.decisions:
        if kinds.get(decision.kind.id) is not decision.kind or decision.kind not in applicable:
            problems.append(f"Decision {decision.kind.id!r} does not apply to this document family")
            continue
        if decision.target is not None and decision.kind.domain is not None:
            try:
                domain = decision.kind.domain
                if domain not in indices:
                    indices[domain] = domain.inspect(document)
                current = indices[domain].binding(decision.target.path)
            except PlanError as error:
                problems.append(f"{decision.kind.id} @ {decision.target.path}: {error.message}")
                continue
            if current.fingerprint != decision.target.fingerprint:
                problems.append(
                    f"{decision.kind.id} @ {decision.target.path}: fingerprint mismatch"
                )
    if problems:
        message = "Plan answers do not match the source"
        raise PlanError(message, problems=tuple(problems), remedy=Remedy(RemedyAction.REBIND_PLAN))
    _kind_constraints(document, plan.decisions)
    return tuple(
        sorted(
            plan.decisions,
            key=lambda decision: (
                positions[decision.kind.id],
                decision.target.path if decision.target else "",
            ),
        )
    )


def _kind_constraints(document: OdfDocument, decisions: tuple[Decision, ...]) -> None:
    for decision in decisions:
        for check in decision.kind.constraints.checks:
            check(document, decision, decisions)
