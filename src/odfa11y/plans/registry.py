# SPDX-License-Identifier: MPL-2.0
"""Collect the decision contracts explicitly declared by document families."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, cast

from odfa11y.decisions import OpenDecision
from odfa11y.decisions.kinds import COMMON_KINDS
from odfa11y.decisions.validation import ANSWER_FORMATS
from odfa11y.errors import PlanError
from odfa11y.families import REGISTRY
from odfa11y.report import RULES, FactKeys

from .codec import parse_plan

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from _typeshed import DataclassInstance

    from odfa11y.decisions import DecisionKind
    from odfa11y.plans.models import Plan
    from odfa11y.report import Report


def registered_kinds() -> dict[str, DecisionKind]:
    """Collect kinds, refusing conflicting descriptions of a shared identity.

    Returns
    -------
    dict[str, DecisionKind]
        All bundled common/family kinds in canonical registration order.

    Raises
    ------
    PlanError
        Families register incompatible meanings for the same decision identity.

    """
    result = {kind.id: kind for kind in COMMON_KINDS}
    for adapter in REGISTRY.values():
        for kind in adapter.decision_kinds:
            if kind.id in result and result[kind.id] != kind:
                msg = f"Conflicting registrations for decision {kind.id}"
                raise PlanError(msg)
            result[kind.id] = kind
    return dict(sorted(result.items()))


def registered_formats() -> dict[str, Callable[[str], object]]:
    """Expose the same scalar format checks used by the strict answer codec.

    Returns
    -------
    dict[str, Callable[[str], object]]
        Builtin and family-declared string format validators.

    Raises
    ------
    PlanError
        The same format identity has conflicting validators.

    """
    result: dict[str, Callable[[str], object]] = dict(ANSWER_FORMATS)
    for kind in registered_kinds().values():
        for field in dataclasses.fields(cast("type[DataclassInstance]", kind.answer_type)):
            name = field.metadata.get("schema", {}).get("format")
            validator = field.metadata.get("validate")
            if name and validator:
                if name in result and result[name] is not validator:
                    msg = f"Conflicting answer format {name}"
                    raise PlanError(msg)
                result[name] = validator
    return result


def load_plan(path: str | Path) -> Plan:
    """Read a plan using all explicitly registered family contracts.

    Returns
    -------
    Plan
        The strict source-bound plan.

    """
    return parse_plan(path, registered_kinds())


def document_decisions(report: Report) -> None:
    """Attach common document questions using registered rules and typed facts."""
    for kind in COMMON_KINDS:
        rules = tuple(
            finding.rule_id
            for finding in report.findings
            if kind.id in RULES[finding.rule_id].decision_kinds
        )
        if rules:
            current = (
                {
                    "title": report.facts.get(FactKeys.DOCUMENT_TITLE),
                    "description": report.facts.get(FactKeys.DOCUMENT_DESCRIPTION),
                    "language": report.facts.get(FactKeys.DOCUMENT_LANGUAGE),
                }
                if kind.id == "document.metadata"
                else {"version": report.facts.get(FactKeys.DOCUMENT_ODF_VERSION)}
            )
            report.add_decision(OpenDecision(kind, None, None, current, rules))
