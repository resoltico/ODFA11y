# SPDX-License-Identifier: MPL-2.0
"""Image alternative answers translated into guarded graphic edits."""

lazy from collections.abc import Sequence

from odfa11y.concepts import GraphicAlternative
from odfa11y.decisions.answers import GraphicAlternativeAnswer
from odfa11y.decisions.kind import GRAPHIC_ALTERNATIVE
from odfa11y.families.image.operations import SetGraphicAlternatives
lazy from odfa11y.concepts.edits import Operation
lazy from odfa11y.decisions import Decision
lazy from odfa11y.odf import OdfDocument

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
