# SPDX-License-Identifier: MPL-2.0
"""Cross-family decision kinds with one shared answer contract."""

from odfa11y.concepts.domains import GRAPHICS, LINKS, PAGES
from odfa11y.concepts.graphics import edit_graphic
from odfa11y.concepts.links import edit_link
from odfa11y.concepts.pages import edit_page_metadata, edit_page_navigation
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
    edit=edit_graphic,
    resolves=(
        rules.GRAPHIC001,
        rules.GRAPHIC002,
    ),
)
LINK_DESCRIPTION = DecisionKind(
    "link.description",
    DecisionScope.TARGET,
    LinkDescriptionAnswer,
    domain=LINKS,
    edit=edit_link,
    resolves=(rules.LINK003,),
)
PAGE_METADATA = DecisionKind(
    "page.metadata",
    DecisionScope.TARGET,
    PageMetadataAnswer,
    domain=PAGES,
    edit=edit_page_metadata,
    resolves=(rules.PAGE003,),
)
PAGE_NAVIGATION = DecisionKind(
    "page.navigation",
    DecisionScope.TARGET,
    PageNavigationAnswer,
    domain=PAGES,
    edit=edit_page_navigation,
    resolves=(
        rules.PAGE004,
        rules.PAGE005,
    ),
)
