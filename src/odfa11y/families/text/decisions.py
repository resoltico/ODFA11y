# SPDX-License-Identifier: MPL-2.0
"""Writer answer contracts and translation into preservation-guarded operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from odfa11y.content import GraphicAlternative, LinkDescription
from odfa11y.decisions import DecisionKind, DecisionScope
from odfa11y.decisions.answers import GraphicAlternativeAnswer, LinkDescriptionAnswer, SwitchAnswer
from odfa11y.decisions.kinds import GRAPHIC_ALTERNATIVE, LINK_DESCRIPTION
from odfa11y.decisions.validation import LANGUAGE_TAG_FORMAT
from odfa11y.odf import Family

from .graphics import SetGraphicAlternatives, SetLinkDescriptions
from .headings import MAX_HEADING_LEVEL, HeadingLevel, SetHeadingLevels
from .language.operations import SetTargetLanguages, TargetLanguage
from .linkify import LinkifyAddresses
from .remove_spacers import RemoveEmptySpacers
from .spacing import NormalizeSpacing
from .tables import MarkTableHeaders, TableHeaders

if TYPE_CHECKING:
    from collections.abc import Sequence

    from odfa11y.adapter import Operation
    from odfa11y.decisions import Decision
    from odfa11y.odf import OdfDocument


@dataclass(frozen=True, slots=True)
class TargetLanguageAnswer:
    """Explicit language overrides for one paragraph or inline reading target."""

    western: str | None = field(default=None, metadata={"schema": {"format": LANGUAGE_TAG_FORMAT}})
    asian: str | None = field(default=None, metadata={"schema": {"format": LANGUAGE_TAG_FORMAT}})
    complex: str | None = field(default=None, metadata={"schema": {"format": LANGUAGE_TAG_FORMAT}})
    required_any: ClassVar[tuple[str, ...]] = ("western", "asian", "complex")


@dataclass(frozen=True, slots=True)
class HeadingLevelAnswer:
    """The reviewed semantic level of one heading."""

    level: int = field(
        metadata={
            "schema": {
                "minimum": 1,
                "maximum": MAX_HEADING_LEVEL,
                "description": "Intended outline level.",
            }
        }
    )


@dataclass(frozen=True, slots=True)
class TableHeadersAnswer:
    """Explicit semantic header bands for a safely resolved table."""

    rows: int | None = field(
        default=None,
        metadata={
            "schema": {"minimum": 1, "description": "Number of leading logical header rows."}
        },
    )
    columns: int | None = field(
        default=None,
        metadata={
            "schema": {"minimum": 1, "description": "Number of leading logical header columns."}
        },
    )
    required_any: ClassVar[tuple[str, ...]] = ("rows", "columns")


@dataclass(frozen=True, slots=True)
class TextSpacingAnswer:
    """Reviewed reference text and the paragraph styles whose spacing may change."""

    reference_text: str = field(
        metadata={
            "schema": {
                "pattern": r"\S",
                "description": "Authored text identifying the reference paragraph.",
            }
        }
    )
    target_styles: tuple[str, ...] = field(
        metadata={
            "schema": {
                "minItems": 1,
                "items": {"type": "string", "pattern": r"\S"},
                "description": "Existing paragraph styles selected for spacing normalization.",
            }
        }
    )
    exact_reference: bool = field(
        default=False, metadata={"schema": {"description": "Match the entire reference paragraph."}}
    )
    include_headings: bool = field(
        default=False,
        metadata={"schema": {"description": "Also apply to headings using the selected styles."}},
    )


FAMILIES = frozenset({Family.TEXT})
LINKIFY_ADDRESSES = DecisionKind(
    "text.linkify_addresses", DecisionScope.DOCUMENT, SwitchAnswer, FAMILIES, LinkifyAddresses.name
)
REMOVE_SPACERS = DecisionKind(
    "text.remove_spacers", DecisionScope.DOCUMENT, SwitchAnswer, FAMILIES, RemoveEmptySpacers.name
)
HEADING_LEVEL = DecisionKind(
    "heading.level", DecisionScope.TARGET, HeadingLevelAnswer, FAMILIES, SetHeadingLevels.name
)
TABLE_HEADERS = DecisionKind(
    "table.headers", DecisionScope.TARGET, TableHeadersAnswer, FAMILIES, MarkTableHeaders.name
)
TEXT_SPACING = DecisionKind(
    "text.spacing", DecisionScope.DOCUMENT, TextSpacingAnswer, FAMILIES, NormalizeSpacing.name
)
TARGET_LANGUAGE = DecisionKind(
    "language.target", DecisionScope.TARGET, TargetLanguageAnswer, FAMILIES, SetTargetLanguages.name
)
DECISION_KINDS = (
    LINKIFY_ADDRESSES,
    REMOVE_SPACERS,
    GRAPHIC_ALTERNATIVE,
    HEADING_LEVEL,
    TABLE_HEADERS,
    TEXT_SPACING,
    LINK_DESCRIPTION,
    TARGET_LANGUAGE,
)


def operations(document: OdfDocument, decisions: Sequence[Decision]) -> tuple[Operation, ...]:
    """Compile canonical reviewed answers, without parsing any persisted tables.

    Returns
    -------
    tuple[Operation, ...]
        Deterministic per-decision operations.

    """
    del document
    result = []
    for decision in decisions:
        if decision.kind in {LINKIFY_ADDRESSES, REMOVE_SPACERS}:
            if decision.answer_as(SwitchAnswer).enabled:
                result.append(
                    LinkifyAddresses()
                    if decision.kind == LINKIFY_ADDRESSES
                    else RemoveEmptySpacers()
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
        elif decision.kind == HEADING_LEVEL:
            result.append(
                SetHeadingLevels({
                    decision.target_path: HeadingLevel(
                        decision.answer_as(HeadingLevelAnswer).level, decision.fingerprint
                    )
                })
            )
        elif decision.kind == TABLE_HEADERS:
            answer = decision.answer_as(TableHeadersAnswer)
            result.append(
                MarkTableHeaders({
                    decision.target_path: TableHeaders(
                        answer.rows, answer.columns, decision.fingerprint
                    )
                })
            )
        elif decision.kind == TEXT_SPACING:
            answer = decision.answer_as(TextSpacingAnswer)
            result.append(
                NormalizeSpacing(
                    answer.reference_text,
                    answer.target_styles,
                    exact_reference=answer.exact_reference,
                    include_headings=answer.include_headings,
                )
            )
        elif decision.kind == TARGET_LANGUAGE:
            answer = decision.answer_as(TargetLanguageAnswer)
            result.append(
                SetTargetLanguages({
                    decision.target_path: TargetLanguage(
                        answer.western, answer.asian, answer.complex, decision.fingerprint
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
