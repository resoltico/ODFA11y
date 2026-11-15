# SPDX-License-Identifier: MPL-2.0
"""Cross-family decision kinds with one shared answer contract."""

from odfa11y.concepts.domains import GRAPHICS, LINKS, PAGES
from odfa11y.decisions.answers import (
    GraphicAlternativeAnswer,
    LinkDescriptionAnswer,
    PageMetadataAnswer,
    PageNavigationAnswer,
)
from odfa11y.decisions.decision import DecisionKind, DecisionScope
from odfa11y.rules import registry as rules

GRAPHIC_ALTERNATIVE = DecisionKind(
    "graphic.alternative",
    DecisionScope.TARGET,
    GraphicAlternativeAnswer,
    domain=GRAPHICS,
    resolves=(
        rules.GRAPHIC003,
        rules.GRAPHIC005,
    ),
)
LINK_DESCRIPTION = DecisionKind(
    "link.description",
    DecisionScope.TARGET,
    LinkDescriptionAnswer,
    domain=LINKS,
    resolves=(rules.LINK003,),
)
PAGE_METADATA = DecisionKind(
    "page.metadata",
    DecisionScope.TARGET,
    PageMetadataAnswer,
    domain=PAGES,
    resolves=(rules.PAGE002,),
)
PAGE_NAVIGATION = DecisionKind(
    "page.navigation",
    DecisionScope.TARGET,
    PageNavigationAnswer,
    domain=PAGES,
    resolves=(
        rules.PAGE003,
        rules.PAGE004,
    ),
)
