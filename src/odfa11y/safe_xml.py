# SPDX-License-Identifier: MPL-2.0
"""Parse untrusted XML without entity expansion or network access."""

from __future__ import annotations

from lxml import etree


def secure_xml_parser() -> etree.XMLParser:
    """Disable XML external entities, network access and permissive parsing.

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
        huge_tree=False,
    )
