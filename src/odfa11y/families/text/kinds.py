# SPDX-License-Identifier: MPL-2.0
"""Writer answer contracts and translation into preservation-guarded operations."""

from dataclasses import dataclass
from typing import Annotated, ClassVar
lazy from collections.abc import Sequence

from odfa11y.concepts import GraphicAlternative, LinkDescription
from odfa11y.contracts import (
    Description,
    ItemCount,
    LanguageTag,
    NonBlank,
    Range,
    RequireAny,
)
from odfa11y.decisions import DecisionKind, DecisionScope
from odfa11y.decisions.answers import GraphicAlternativeAnswer, LinkDescriptionAnswer, SwitchAnswer
from odfa11y.decisions.kind import GRAPHIC_ALTERNATIVE, LINK_DESCRIPTION
from odfa11y.families.text.graphics import SetGraphicAlternatives, SetLinkDescriptions
from odfa11y.families.text.headings.edit import (
    MAX_HEADING_LEVEL,
    HeadingLevel,
    SetHeadingLevels,
)
from odfa11y.families.text.language.operations import SetTargetLanguages, TargetLanguage
from odfa11y.families.text.links.edit import LinkifyAddresses
from odfa11y.families.text.spacing.edit import NormalizeSpacing
from odfa11y.families.text.spacing.remove import RemoveEmptySpacers
from odfa11y.families.text.tables import MarkTableHeaders, TableHeaders
from odfa11y.odf import Family
from odfa11y.targets import require_target
lazy from odfa11y.concepts.edits import Operation
lazy from odfa11y.decisions import Decision
lazy from odfa11y.odf import OdfDocument


@dataclass(frozen=True, slots=True)
class TargetLanguageAnswer:
    """Explicit language overrides for one paragraph or inline reading target."""

    western: Annotated[
        str | None, LanguageTag(), Description("Language for the target western-script channel.")
    ] = None
    asian: Annotated[
        str | None, LanguageTag(), Description("Language for the target Asian-script channel.")
    ] = None
    complex: Annotated[
        str | None, LanguageTag(), Description("Language for the target complex-script channel.")
    ] = None
    __contract__: ClassVar[Annotated[object, RequireAny(("western", "asian", "complex"))]]


@dataclass(frozen=True, slots=True)
class HeadingLevelAnswer:
    """The reviewed semantic level of one heading."""

    level: Annotated[
        int, Range(minimum=1, maximum=MAX_HEADING_LEVEL), Description("Intended outline level.")
    ]


@dataclass(frozen=True, slots=True)
class TableHeadersAnswer:
    """Explicit semantic header bands for a safely resolved table."""

    rows: Annotated[
        int | None, Range(minimum=1), Description("Number of leading logical header rows.")
    ] = None
    columns: Annotated[
        int | None, Range(minimum=1), Description("Number of leading logical header columns.")
    ] = None
    __contract__: ClassVar[Annotated[object, RequireAny(("rows", "columns"))]]


@dataclass(frozen=True, slots=True)
class TextSpacingAnswer:
    """Reviewed reference text and the paragraph styles whose spacing may change."""

    reference_text: Annotated[
        str, NonBlank(), Description("Authored text identifying the reference paragraph.")
    ]
    target_styles: Annotated[
        tuple[Annotated[str, NonBlank()], ...],
        ItemCount(minimum=1),
        Description("Existing paragraph styles selected for spacing normalization."),
    ]
    exact_reference: Annotated[bool, Description("Match the entire reference paragraph.")] = False
    include_headings: Annotated[
        bool, Description("Also apply to headings using the selected styles.")
    ] = False


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
                        answer.title,
                        answer.description,
                        require_target(decision.target).fingerprint,
                        answer.decorative,
                    )
                })
            )
        elif decision.kind == HEADING_LEVEL:
            result.append(
                SetHeadingLevels({
                    decision.target_path: HeadingLevel(
                        decision.answer_as(HeadingLevelAnswer).level,
                        require_target(decision.target).fingerprint,
                    )
                })
            )
        elif decision.kind == TABLE_HEADERS:
            answer = decision.answer_as(TableHeadersAnswer)
            result.append(
                MarkTableHeaders({
                    decision.target_path: TableHeaders(
                        answer.rows, answer.columns, require_target(decision.target).fingerprint
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
                        answer.western,
                        answer.asian,
                        answer.complex,
                        require_target(decision.target).fingerprint,
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
