# SPDX-License-Identifier: MPL-2.0
"""Reviewed sheet, graphic and link answer contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from odfa11y.content import GraphicAlternative, LinkDescription
from odfa11y.decisions import DecisionKind, DecisionScope
from odfa11y.decisions.answers import GraphicAlternativeAnswer, LinkDescriptionAnswer
from odfa11y.decisions.kinds import GRAPHIC_ALTERNATIVE, LINK_DESCRIPTION
from odfa11y.decisions.validation import validate_xml_text
from odfa11y.odf import Family

from .names import SetSheetNames, SheetNameChange, invalid_name_reason
from .objects import SetGraphicAlternatives, SetLinkDescriptions

if TYPE_CHECKING:
    from collections.abc import Sequence

    from odfa11y.adapter import Operation
    from odfa11y.decisions import Decision
    from odfa11y.odf import OdfDocument


def validate_sheet_name(name: str) -> None:
    """Require native-safe names without accepting invalid XML text.

    Raises
    ------
    ValueError
        The name cannot be represented or violates native naming constraints.

    """
    validate_xml_text(name)
    if reason := invalid_name_reason(name):
        raise ValueError(reason)


@dataclass(frozen=True, slots=True)
class SheetNameAnswer:
    """A meaningful sheet name supplied by its reviewer."""

    name: str = field(
        metadata={
            "schema": {
                "format": "odfa11y-sheet-name",
                "description": "Name identifying what the sheet contains.",
            },
            "validate": validate_sheet_name,
        }
    )


SHEET_NAME = DecisionKind(
    "sheet.name",
    DecisionScope.TARGET,
    SheetNameAnswer,
    frozenset({Family.SPREADSHEET}),
    SetSheetNames.name,
)
DECISION_KINDS = (SHEET_NAME, GRAPHIC_ALTERNATIVE, LINK_DESCRIPTION)


def operations(document: OdfDocument, decisions: Sequence[Decision]) -> tuple[Operation, ...]:
    """Compile exact reviewed identities without parsing family tables.

    Returns
    -------
    tuple[Operation, ...]
        Per-decision sheet and metadata edits.

    """
    del document
    result = []
    for decision in decisions:
        if decision.kind == SHEET_NAME:
            answer = decision.answer_as(SheetNameAnswer)
            result.append(
                SetSheetNames({
                    decision.target_path: SheetNameChange(answer.name, decision.fingerprint or "")
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
