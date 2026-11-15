# SPDX-License-Identifier: MPL-2.0
"""Select ODF elements with XPath, returning only element nodes."""

from __future__ import annotations

from lxml import etree

from .namespaces import NS


def select_elements(
    node: etree._Element | etree._ElementTree, expression: str
) -> list[etree._Element]:
    """Select the elements matching an XPath expression with the ODF namespace prefixes bound.

    Returns
    -------
    list[etree._Element]
        Matching element nodes in document order; text, attribute and scalar results are dropped.

    """
    result = node.xpath(expression, namespaces=NS)
    if not isinstance(result, list):
        return []
    return [item for item in result if isinstance(item, etree._Element)]
