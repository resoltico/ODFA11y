# SPDX-License-Identifier: MPL-2.0
"""Select styled paragraphs and translate qualified property names."""

lazy from lxml import etree

from odfa11y.errors import RemediationError
from odfa11y.odf import NS, qn
from odfa11y.odf import names as xml_names

SPACING_ATTRIBUTES = (
    xml_names.FO_MARGIN_TOP,
    xml_names.FO_MARGIN_BOTTOM,
    xml_names.FO_LINE_HEIGHT,
    xml_names.FO_LINE_HEIGHT_AT_LEAST,
    xml_names.STYLE_CONTEXTUAL_SPACING,
)

BREAK_ATTRIBUTES = (
    xml_names.FO_BREAK_BEFORE,
    xml_names.FO_BREAK_AFTER,
    xml_names.STYLE_MASTER_PAGE_NAME,
    xml_names.STYLE_PAGE_NUMBER,
)


def paragraph_style_name(node: etree._Element) -> str | None:
    """Select a paragraph's single style only when its precedence is established.

    Returns
    -------
    str | None
        The ordinary style reference, or None for the default style.

    Raises
    ------
    RemediationError
        Class overlays or conditional references require native style review.
    """
    if any(qn("text", name) in node.attrib for name in ("class-names", "cond-style-name")):
        msg = (
            "Paragraph class overlays or conditional style references "
            "cannot establish effective properties."
        )
        raise RemediationError(msg)
    return node.get(xml_names.TEXT_STYLE_NAME)


def display_attr(qname: str) -> str:
    """Render a Clark-notation attribute name with its namespace prefix.

    Returns
    -------
    str
        The prefixed name, or the input when its namespace is unknown.

    """
    for prefix, uri in NS.items():
        marker = f"{{{uri}}}"
        if qname.startswith(marker):
            return f"{prefix}:{qname[len(marker) :]}"
    return qname


def attr_from_display(name: str) -> str:
    """Parse a prefixed attribute name into Clark notation.

    Returns
    -------
    str
        The Clark-notation name, or the input when its prefix is unknown.

    """
    if ":" not in name:
        return name
    prefix, local = name.split(":", 1)
    if prefix not in NS:
        return name
    return qn(prefix, local)
