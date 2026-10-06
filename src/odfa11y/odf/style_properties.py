# SPDX-License-Identifier: MPL-2.0
"""Select styled paragraphs and translate qualified property names."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .namespaces import NS, qn

if TYPE_CHECKING:
    from collections.abc import Iterable

    from lxml import etree


def find_paragraphs_by_style(
    tree: etree._ElementTree,
    style_names: Iterable[str],
    *,
    include_headings: bool = False,
) -> list[etree._Element]:
    """Select paragraphs and optionally headings using named styles.

    Returns
    -------
    list[etree._Element]
        Matching paragraph elements, including headings only when requested.

    """
    wanted = set(style_names)
    xpath = "//text:p" + (" | //text:h" if include_headings else "")
    return [
        p
        for p in tree.xpath(xpath, namespaces=NS)
        if (p.get(qn("text", "style-name")) or "(none)") in wanted
    ]


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
