# SPDX-License-Identifier: AGPL-3.0-only
"""Shared answer fields, constraints and help for cross-family human decisions."""

from dataclasses import dataclass
from typing import Annotated, ClassVar

from odfa11y.contracts import (
    Choices,
    Description,
    ExclusiveWhen,
    LanguageTag,
    NonBlank,
    RequireAny,
    XmlText,
)
from odfa11y.odf import SUPPORTED_VERSIONS


@dataclass(frozen=True, slots=True)
class GraphicAlternativeAnswer:
    """Authored accessible text and an explicit meaning/decorative role."""

    title: Annotated[str | None, XmlText(), NonBlank(), Description("Accessible title.")] = None
    description: Annotated[
        str | None, XmlText(), NonBlank(), Description("Explain the graphic's meaning.")
    ] = None
    decorative: Annotated[
        bool | None, Description("Explicit decorative role, subject to source safety guards.")
    ] = None
    __contract__: ClassVar[
        Annotated[
            object,
            RequireAny(("title", "description", "decorative")),
            ExclusiveWhen("decorative", True, ("title", "description")),
        ]
    ]


@dataclass(frozen=True, slots=True)
class LinkDescriptionAnswer:
    """A supplied description without changing visible text or destination."""

    description: Annotated[
        str,
        XmlText(),
        NonBlank(),
        Description("Explain the link's purpose in its reading context."),
    ]


@dataclass(frozen=True, slots=True)
class PageMetadataAnswer:
    """Explicit page title and purpose."""

    title: Annotated[str | None, XmlText(), NonBlank(), Description("Accessible page title.")] = (
        None
    )
    description: Annotated[
        str | None, XmlText(), NonBlank(), Description("Page purpose and context.")
    ] = None
    __contract__: ClassVar[Annotated[object, RequireAny(("title", "description"))]]


@dataclass(frozen=True, slots=True)
class PageNavigationAnswer:
    """A reviewed complete order of native shape identities."""

    navigation: Annotated[
        tuple[Annotated[str, XmlText(), NonBlank()], ...],
        Description("Complete reading order of the page's existing shape identities."),
    ]


@dataclass(frozen=True, slots=True)
class SwitchAnswer:
    """Explicit consent or refusal for a document-wide operation."""

    enabled: Annotated[bool, Description("Enable only after reviewing all affected content.")]


@dataclass(frozen=True, slots=True)
class FormulaAlternativeAnswer:
    """The spoken meaning of the native mathematical expression."""

    alternative: Annotated[
        str,
        XmlText(),
        NonBlank(),
        Description("Write the formula's spoken meaning in its intended language."),
    ]


@dataclass(frozen=True, slots=True)
class DatabaseDescriptionAnswer:
    """Human-supplied meaning for an existing declared database object."""

    text: Annotated[
        str,
        XmlText(),
        NonBlank(),
        Description("Explain the declared object without changing SQL or bindings."),
    ]


@dataclass(frozen=True, slots=True)
class DocumentMetadataAnswer:
    """Explicit document title, description and default language."""

    title: Annotated[
        str | None, XmlText(), NonBlank(), Description("Document title identifying its purpose.")
    ] = None
    description: Annotated[
        str | None, XmlText(), NonBlank(), Description("Document description and context.")
    ] = None
    language: Annotated[
        str | None,
        LanguageTag(),
        Description("Intended default language, preserving explicit local overrides."),
    ] = None
    __contract__: ClassVar[Annotated[object, RequireAny(("title", "description", "language"))]]


@dataclass(frozen=True, slots=True)
class OdfVersionAnswer:
    """An explicit supported source-version declaration."""

    version: Annotated[
        str,
        Choices(SUPPORTED_VERSIONS),
        Description("ODF version whose result must satisfy schema guards."),
    ]
