# SPDX-License-Identifier: MPL-2.0
"""Extract and compare visible document text."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lxml import etree

    from .package import OdtPackage

from .namespaces import qn
from .xpath import select_elements


def is_empty_paragraph(p: etree._Element) -> bool:
    """Whether a paragraph has no visible text or meaningful inline content.

    Returns
    -------
    bool
        True when the paragraph is empty.

    """
    if element_text(p).strip():
        return False
    meaningful = select_elements(
        p,
        (
            ".//draw:* | .//text:line-break | .//text:tab | "
            ".//text:bookmark | .//text:bookmark-start | "
            ".//text:bookmark-end | .//text:reference-mark | "
            ".//text:reference-mark-start | .//text:reference-mark-end | "
            ".//text:soft-page-break"
        ),
    )
    return not meaningful


def element_text(element: etree._Element) -> str:
    """Concatenate an element's text with non-breaking spaces normalized.

    Returns
    -------
    str
        The stripped text.

    """
    return "".join(element.itertext()).replace("\u00a0", " ").strip()


def visible_text_snapshot(package: OdtPackage) -> tuple[str, ...]:
    """Collect normalized heading and paragraph text from a package's content.

    Returns
    -------
    tuple[str, ...]
        One entry per visible text block.

    """
    tree = package.parse_xml("content.xml")
    blocks: list[str] = []
    for node in select_elements(tree, "//text:h | //text:p"):
        text = _visible_node_text(node).replace("\u00a0", " ")
        blocks.append(" ".join(text.split()))
    return tuple(blocks)


def _visible_node_text(node: etree._Element) -> str:
    """Return rendered textual content while excluding accessibility metadata.

    Returns
    -------
    str
        Rendered text with graphic accessibility metadata excluded.

    """
    pieces: list[str] = []
    if node.text:
        pieces.append(node.text)
    for child in node:
        if child.tag not in {qn("svg", "title"), qn("svg", "desc")}:
            pieces.append(_visible_node_text(child))
        if child.tail:
            pieces.append(child.tail)
    return "".join(pieces)


def text_is_preserved(
    before: tuple[str, ...], after: tuple[str, ...], *, removed_empty_blocks: int = 0
) -> bool:
    """Allow only the specified number of empty-block removals in a text sequence.

    Returns
    -------
    bool
        Whether all remaining block text and its order are unchanged.

    """
    position = 0
    remaining = removed_empty_blocks
    for block in before:
        if position < len(after) and block == after[position]:
            position += 1
        elif not block and remaining > 0:
            remaining -= 1
        else:
            return False
    return position == len(after) and remaining == 0
