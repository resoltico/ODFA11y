# SPDX-License-Identifier: MPL-2.0
"""Read explicit [presentation] decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import config_tables
from odfa11y.content import graphic_alternatives, link_descriptions, page_decisions

from .operations import SetGraphicAlternatives, SetLinkDescriptions, SetPageSemantics

if TYPE_CHECKING:
    from odfa11y.adapter import Operation


def parse_table(data: dict[str, object]) -> list[Operation]:
    """Read page and graphic decisions in a fixed order.

    Returns
    -------
    list[Operation]
        Page semantics followed by graphic descriptions.

    """
    config_tables.known(data, {"pages", "graphics", "links"}, "presentation")
    operations: list[Operation] = []
    pages = page_decisions(config_tables.table(data, "pages"), "presentation.pages")
    graphics = graphic_alternatives(config_tables.table(data, "graphics"), "presentation.graphics")
    if pages:
        operations.append(SetPageSemantics(pages))
    if graphics:
        operations.append(SetGraphicAlternatives(graphics))
    links = link_descriptions(config_tables.table(data, "links"), "presentation.links")
    if links:
        operations.append(SetLinkDescriptions(links))
    return operations
