# SPDX-License-Identifier: MPL-2.0
"""Reviewed database-object description answers and operation translation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.decisions import DecisionKind, DecisionScope
from odfa11y.decisions.answers import DatabaseDescriptionAnswer
from odfa11y.odf import Family

from .descriptions import DatabaseDescription, SetObjectDescriptions

if TYPE_CHECKING:
    from collections.abc import Sequence

    from odfa11y.adapter import Operation
    from odfa11y.decisions import Decision
    from odfa11y.odf import OdfDocument

DATABASE_DESCRIPTION = DecisionKind(
    "database.description",
    DecisionScope.TARGET,
    DatabaseDescriptionAnswer,
    frozenset({Family.DATABASE}),
    SetObjectDescriptions.name,
)
DECISION_KINDS = (DATABASE_DESCRIPTION,)


def operations(document: OdfDocument, decisions: Sequence[Decision]) -> tuple[Operation, ...]:
    """Compile descriptions while preserving queries, values and bindings.

    Returns
    -------
    tuple[Operation, ...]
        Per-target description operations.

    """
    del document
    return tuple(
        SetObjectDescriptions({
            decision.target_path: DatabaseDescription(
                decision.answer_as(DatabaseDescriptionAnswer).text, decision.fingerprint
            )
        })
        for decision in decisions
    )
