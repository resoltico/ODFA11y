# SPDX-License-Identifier: MPL-2.0
"""Reviewed page, navigation, graphic and link answers for drawing documents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.content import GraphicAlternative, LinkDescription, PageDecision
from odfa11y.decisions.answers import (
    GraphicAlternativeAnswer,
    LinkDescriptionAnswer,
    PageMetadataAnswer,
    PageNavigationAnswer,
)
from odfa11y.decisions.kinds import (
    GRAPHIC_ALTERNATIVE,
    LINK_DESCRIPTION,
    PAGE_METADATA,
    PAGE_NAVIGATION,
)

from .operations import SetGraphicAlternatives, SetLinkDescriptions, SetPageSemantics

if TYPE_CHECKING:
    from collections.abc import Sequence

    from odfa11y.adapter import Operation
    from odfa11y.decisions import Decision
    from odfa11y.odf import OdfDocument

DECISION_KINDS = (PAGE_METADATA, PAGE_NAVIGATION, GRAPHIC_ALTERNATIVE, LINK_DESCRIPTION)


def operations(document: OdfDocument, decisions: Sequence[Decision]) -> tuple[Operation, ...]:
    """Translate reviewed answers without parsing persisted tables.

    Returns
    -------
    tuple[Operation, ...]
        Per-decision operations with mandatory reviewed identities.

    """
    del document
    result = []
    for decision in decisions:
        if decision.kind == PAGE_METADATA:
            answer = decision.answer_as(PageMetadataAnswer)
            result.append(
                SetPageSemantics({
                    decision.target_path: PageDecision(
                        answer.title, answer.description, fingerprint=decision.fingerprint
                    )
                })
            )
        elif decision.kind == PAGE_NAVIGATION:
            answer = decision.answer_as(PageNavigationAnswer)
            result.append(
                SetPageSemantics({
                    decision.target_path: PageDecision(
                        navigation=answer.navigation, fingerprint=decision.fingerprint
                    )
                })
            )
        elif decision.kind == GRAPHIC_ALTERNATIVE:
            answer = decision.answer_as(GraphicAlternativeAnswer)
            result.append(
                SetGraphicAlternatives({
                    decision.target_path: GraphicAlternative(
                        answer.title, answer.description, decision.fingerprint, answer.decorative
                    )
                })
            )
        elif decision.kind == LINK_DESCRIPTION:
            answer = decision.answer_as(LinkDescriptionAnswer)
            result.append(
                SetLinkDescriptions({
                    decision.target_path: LinkDescription(
                        answer.description, decision.fingerprint or ""
                    )
                })
            )
    return tuple(result)
