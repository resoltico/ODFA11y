# SPDX-License-Identifier: MPL-2.0
"""Canonical page and sheet locations shared by audits and operation preflight."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.odf import Part, qn
from odfa11y.report import Location

if TYPE_CHECKING:
    from lxml import etree


def page_location(page: etree._Element, index: int) -> Location:
    """Address an authored page name, or its ordinal when the name is absent.

    Returns
    -------
    Location
        The stable logical page address.

    """
    name = page.get(qn("draw", "name"))
    return (
        Location.named(Part.CONTENT, "page", name)
        if name
        else Location.indexed(Part.CONTENT, "page", index)
    )


def sheet_location(index: int) -> Location:
    """Address sheet identity independently of the name a reviewed answer may change.

    Returns
    -------
    Location
        A one-based logical sheet address.

    """
    return Location.indexed(Part.CONTENT, "sheet", index)
