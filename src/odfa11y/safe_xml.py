# SPDX-License-Identifier: MPL-2.0
"""Parse untrusted XML without entity expansion or network access, within a depth limit."""

from __future__ import annotations

from lxml import etree

MAX_DEPTH = 256


def secure_xml_parser() -> etree.XMLParser:
    """Disable XML external entities, network access and permissive parsing.

    Very large text nodes (an embedded base64 image) are allowed; entity expansion stays
    off, input size is bounded by the callers, and :func:`parse_secure` bounds the depth.

    Returns
    -------
    etree.XMLParser
        A parser that rejects external entities and network access.

    """
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        recover=False,
        remove_blank_text=False,
        huge_tree=True,
    )


def parse_secure(data: bytes) -> etree._Element:
    """Parse bytes with the secure parser and refuse a document nested too deeply.

    Returns
    -------
    etree._Element
        The root element.

    Raises
    ------
    etree.XMLSyntaxError
        The data is malformed or nests deeper than ``MAX_DEPTH`` elements.

    """
    root = etree.fromstring(data.lstrip(b" \t\r\n"), parser=secure_xml_parser())
    stack = [(root, 1)]
    while stack:
        element, depth = stack.pop()
        if depth > MAX_DEPTH:
            msg = f"XML is nested deeper than {MAX_DEPTH} elements"
            raise etree.XMLSyntaxError(msg, 0, 0, 0)
        stack.extend((child, depth + 1) for child in element if isinstance(child.tag, str))
    return root
