# SPDX-License-Identifier: MPL-2.0
"""Compile bound decision plans into common and family-owned operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.decisions.answers import DocumentMetadataAnswer, OdfVersionAnswer
from odfa11y.decisions.kinds import COMMON_KINDS
from odfa11y.errors import PlanError
from odfa11y.families import adapter_for
from odfa11y.plans.registry import registered_kinds

from .metadata import SetMetadata
from .version import SetOdfVersion

if TYPE_CHECKING:
    from odfa11y.adapter import Operation
    from odfa11y.odf import OdfDocument
    from odfa11y.plans import Plan


def compile_operations(document: OdfDocument, plan: Plan) -> tuple[Operation, ...]:
    """Refuse foreign kinds and compile answers in a stable dependency order.

    Returns
    -------
    tuple[Operation, ...]
        Common operations followed by the selected family's operations.

    Raises
    ------
    PlanError
        A kind is unregistered, belongs to another family or lacks an implementation.

    """
    kinds = registered_kinds()
    adapter = adapter_for(document.kind)
    family = document.kind.family if document.kind else None
    for decision in plan.decisions:
        if kinds.get(decision.kind.id) is not decision.kind or family not in decision.kind.families:
            msg = f"Decision {decision.kind.id!r} does not apply to this document family"
            raise PlanError(msg)
    positions = {
        kind.id: index for index, kind in enumerate((*COMMON_KINDS, *adapter.decision_kinds))
    }
    decisions = sorted(
        plan.decisions,
        key=lambda decision: (
            positions[decision.kind.id],
            decision.target.path if decision.target else "",
        ),
    )
    result: list[Operation] = []
    remaining = []
    for decision in decisions:
        if decision.kind.id == "document.odf_version":
            result.append(SetOdfVersion(decision.answer_as(OdfVersionAnswer).version))
        elif decision.kind.id == "document.metadata":
            answer = decision.answer_as(DocumentMetadataAnswer)
            result.append(SetMetadata(answer.title, answer.description, answer.language))
        else:
            remaining.append(decision)
    if remaining:
        result.extend(adapter.operations(document, remaining))
    return tuple(result)
