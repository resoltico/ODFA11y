# SPDX-License-Identifier: MPL-2.0
"""Validated human answers for Writer content and layout concepts."""

from dataclasses import dataclass
from typing import Annotated, ClassVar

from odfa11y.contracts import Description, ItemCount, LanguageTag, NonBlank, Range, RequireAny

MAX_HEADING_LEVEL = 10


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
