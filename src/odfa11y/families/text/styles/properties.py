# SPDX-License-Identifier: MPL-2.0
"""Select styled paragraphs and translate qualified property names."""

lazy from lxml import etree

from odfa11y.errors import DocumentRefusal
from odfa11y.odf import names as xml_names
from odfa11y.odf import qn


def paragraph_style_name(node: etree._Element) -> str | None:
    """Select a paragraph's single style only when its precedence is established.

    Returns
    -------
    str | None
        The ordinary style reference, or None for the default style.

    Raises
    ------
    DocumentRefusal
        Class overlays or conditional references require native style review.
    """
    if any(qn("text", name) in node.attrib for name in ("class-names", "cond-style-name")):
        msg = (
            "Paragraph class overlays or conditional style references "
            "cannot establish effective properties."
        )
        raise DocumentRefusal(msg)
    return node.get(xml_names.TEXT_STYLE_NAME)
