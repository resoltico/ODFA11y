# SPDX-License-Identifier: AGPL-3.0-only
"""Select ODF elements with XPath, returning only element nodes."""

from lxml import etree

from odfa11y.odf.names import NS


def select_elements(
    node: etree._Element | etree._ElementTree, expression: str, **variables: str
) -> list[etree._Element]:
    """Select the elements matching an XPath expression with the ODF namespace prefixes bound.

    Returns
    -------
    list[etree._Element]
        Matching element nodes in document order; text, attribute and scalar results are dropped.

    """
    result = etree.XPath(expression, namespaces=NS)(node, **variables)
    if not isinstance(result, list):
        return []
    return [item for item in result if isinstance(item, etree._Element)]
