# SPDX-License-Identifier: MPL-2.0
"""Reviewed sheet, graphic and link answer contracts."""

from dataclasses import dataclass
from typing import Annotated, ClassVar
lazy from collections.abc import Sequence

from odfa11y.concepts import GraphicAlternative, LinkDescription
from odfa11y.contracts import (
    Constraint,
    Description,
    XmlText,
)
from odfa11y.decisions import DecisionKind, DecisionScope
from odfa11y.decisions.answers import GraphicAlternativeAnswer, LinkDescriptionAnswer
from odfa11y.decisions.kind import GRAPHIC_ALTERNATIVE, LINK_DESCRIPTION
from odfa11y.families.spreadsheet.names import SetSheetNames, SheetNameChange, invalid_name_reason
from odfa11y.families.spreadsheet.objects import SetGraphicAlternatives, SetLinkDescriptions
from odfa11y.odf import Family
from odfa11y.targets import require_target
lazy from odfa11y.concepts.edits import Operation
lazy from odfa11y.decisions import Decision
lazy from odfa11y.odf import OdfDocument


@dataclass(frozen=True, slots=True)
class SheetName(Constraint):
    """A native sheet name whose characters are representable in XML."""

    format_name: ClassVar[str] = "odfa11y-sheet-name"

    def problems(self, value: object) -> tuple[str, ...]:
        if not isinstance(value, str):
            return ()
        problem = invalid_name_reason(value)
        return XmlText().problems(value) + ((problem,) if problem else ())

    def schema(self) -> dict[str, object]:
        return {"format": self.format_name}


@dataclass(frozen=True, slots=True)
class SheetNameAnswer:
    """A meaningful sheet name supplied by its reviewer."""

    name: Annotated[str, SheetName(), Description("Name identifying what the sheet contains.")]


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
                    decision.target_path: SheetNameChange(
                        answer.name, require_target(decision.target).fingerprint
                    )
                })
            )
        elif decision.kind == GRAPHIC_ALTERNATIVE:
            answer = decision.answer_as(GraphicAlternativeAnswer)
            result.append(
                SetGraphicAlternatives({
                    decision.target_path: GraphicAlternative(
                        answer.title,
                        answer.description,
                        require_target(decision.target).fingerprint,
                        answer.decorative,
                    )
                })
            )
        elif decision.kind == LINK_DESCRIPTION:
            answer = decision.answer_as(LinkDescriptionAnswer)
            result.append(
                SetLinkDescriptions({
                    decision.target_path: LinkDescription(
                        answer.description, require_target(decision.target).fingerprint
                    )
                })
            )
    return tuple(result)
