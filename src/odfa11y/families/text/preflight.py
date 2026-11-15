# SPDX-License-Identifier: MPL-2.0
"""Whole-plan refusals before any supported text operation mutates XML."""

lazy from collections.abc import Sequence

from odfa11y.concepts.kinds import LINK_DESCRIPTION
from odfa11y.decisions.answers import DocumentMetadataAnswer
from odfa11y.errors import DocumentRefusal
from odfa11y.families.text.contexts import has_revisions
from odfa11y.families.text.kinds import (
    LINKIFY_ADDRESSES,
    REMOVE_SPACERS,
    TABLE_HEADERS,
    TARGET_LANGUAGE,
)
from odfa11y.odf import Part
lazy from odfa11y.decisions import Decision
lazy from odfa11y.odf import OdfDocument


def preflight_text(document: OdfDocument, operations: Sequence[Decision]) -> None:
    """Reject revision editing and unstable ordinal target combinations.

    Raises
    ------
    DocumentRefusal
        A plan includes unsupported effects or unstable ordinal targeting.

    """
    if has_revisions(document.tree(Part.CONTENT)) and any(
        not isinstance(decision.answer, DocumentMetadataAnswer)
        or decision.answer.language is not None
        for decision in operations
    ):
        message = (
            "Tracked revisions permit only title/description metadata edits; nothing was written."
        )
        raise DocumentRefusal(message)
    kinds = {decision.kind for decision in operations}
    if TARGET_LANGUAGE in kinds and kinds & {LINKIFY_ADDRESSES, TABLE_HEADERS, REMOVE_SPACERS}:
        message = "Ordinal target languages require a separate reviewed structural plan."
        raise DocumentRefusal(message)
    if kinds & {LINKIFY_ADDRESSES, TABLE_HEADERS}:
        for decision in operations:
            if decision.kind is LINK_DESCRIPTION and "[id=" not in decision.target_path:
                message = "Ordinal link descriptions require a separate reviewed structural plan."
                raise DocumentRefusal(message)
