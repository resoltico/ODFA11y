# SPDX-License-Identifier: AGPL-3.0-only
"""Canonical page and sheet locations shared by audits and operation preflight."""

lazy from lxml import etree

from odfa11y.odf import Part
from odfa11y.odf import names as xml_names
from odfa11y.report import Location


def page_location(page: etree._Element, index: int) -> Location:
    """Address an authored page name, or its ordinal when the name is absent.

    Returns
    -------
    Location
        The stable logical page address.

    """
    name = page.get(xml_names.DRAW_NAME)
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
