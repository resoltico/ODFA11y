# SPDX-License-Identifier: MPL-2.0
"""Cross-family decision kinds with one shared answer contract."""

from __future__ import annotations

from odfa11y.odf import Family

from .answers import (
    DocumentMetadataAnswer,
    GraphicAlternativeAnswer,
    LinkDescriptionAnswer,
    OdfVersionAnswer,
    PageMetadataAnswer,
    PageNavigationAnswer,
)
from .models import DecisionKind, DecisionScope

COMMON_KINDS = (
    DecisionKind(
        "document.odf_version",
        DecisionScope.DOCUMENT,
        OdfVersionAnswer,
        frozenset(Family),
        "set_odf_version",
    ),
    DecisionKind(
        "document.metadata",
        DecisionScope.DOCUMENT,
        DocumentMetadataAnswer,
        frozenset(Family),
        "set_metadata",
    ),
)
GRAPHIC_ALTERNATIVE = DecisionKind(
    "graphic.alternative",
    DecisionScope.TARGET,
    GraphicAlternativeAnswer,
    frozenset({
        Family.TEXT,
        Family.SPREADSHEET,
        Family.PRESENTATION,
        Family.GRAPHICS,
        Family.IMAGE,
    }),
    "set_graphic_alternatives",
)
LINK_DESCRIPTION = DecisionKind(
    "link.description",
    DecisionScope.TARGET,
    LinkDescriptionAnswer,
    frozenset({Family.TEXT, Family.SPREADSHEET, Family.PRESENTATION, Family.GRAPHICS}),
    "set_link_descriptions",
)
PAGE_METADATA = DecisionKind(
    "page.metadata",
    DecisionScope.TARGET,
    PageMetadataAnswer,
    frozenset({Family.PRESENTATION, Family.GRAPHICS}),
    "set_page_semantics",
)
PAGE_NAVIGATION = DecisionKind(
    "page.navigation",
    DecisionScope.TARGET,
    PageNavigationAnswer,
    frozenset({Family.PRESENTATION, Family.GRAPHICS}),
    "set_page_semantics",
)
