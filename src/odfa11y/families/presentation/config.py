# SPDX-License-Identifier: MPL-2.0
"""Read explicit [presentation] decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import config_tables
from odfa11y.content import graphic_descriptions, page_decisions

from .operations import SetGraphicDescriptions, SetPageSemantics

if TYPE_CHECKING:
    from odfa11y.adapter import Operation


def parse_table(data: dict[str, object]) -> list[Operation]:
    """Read page and graphic decisions in a fixed order.

    Returns
    -------
    list[Operation]
        Page semantics followed by graphic descriptions.

    """
    config_tables.known(data, {"pages", "graphics"}, "presentation")
    operations: list[Operation] = []
    pages = page_decisions(config_tables.table(data, "pages"), "presentation.pages")
    graphics = graphic_descriptions(config_tables.table(data, "graphics"), "presentation.graphics")
    if pages:
        operations.append(SetPageSemantics(pages))
    if graphics:
        operations.append(SetGraphicDescriptions(graphics))
    return operations
