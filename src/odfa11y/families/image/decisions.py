# SPDX-License-Identifier: MPL-2.0
"""Image alternative answers translated into guarded graphic edits."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.content import GraphicAlternative
from odfa11y.decisions.answers import GraphicAlternativeAnswer
from odfa11y.decisions.kinds import GRAPHIC_ALTERNATIVE

from .operations import SetGraphicAlternatives

if TYPE_CHECKING:
    from collections.abc import Sequence

    from odfa11y.adapter import Operation
    from odfa11y.decisions import Decision
    from odfa11y.odf import OdfDocument

DECISION_KINDS = (GRAPHIC_ALTERNATIVE,)


def operations(document: OdfDocument, decisions: Sequence[Decision]) -> tuple[Operation, ...]:
    """Compile reviewed text and roles without changing resource identities.

    Returns
    -------
    tuple[Operation, ...]
        Per-target graphic operations.

    """
    del document
    result = []
    for decision in decisions:
        answer = decision.answer_as(GraphicAlternativeAnswer)
        result.append(
            SetGraphicAlternatives({
                decision.target_path: GraphicAlternative(
                    answer.title, answer.description, decision.fingerprint, answer.decorative
                )
            })
        )
    return tuple(result)
