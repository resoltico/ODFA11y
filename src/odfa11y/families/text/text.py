# SPDX-License-Identifier: MPL-2.0
"""Extract and compare the visible text of a text document."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lxml import etree

from odfa11y.odf import qn, select_elements

INERT_INLINE_TAGS = frozenset({qn("text", "span"), qn("text", "s")})
HIDDEN_TAGS = frozenset({qn("svg", "title"), qn("svg", "desc")})


def is_empty_paragraph(p: etree._Element) -> bool:
    """Whether a paragraph has no text and nothing but inert inline elements.

    Anything else (a frame, bookmark, tab, field, change marker, index entry, ...) means the
    paragraph may carry meaning, so it is not a spacer; only an allow-list of inert elements
    counts as empty.

    Returns
    -------
    bool
        True when the paragraph is empty.

    """
    if element_text(p).strip():
        return False
    return all(child.tag in INERT_INLINE_TAGS for child in p.iter("*") if child is not p)


def element_text(element: etree._Element) -> str:
    """Concatenate an element's text with non-breaking spaces normalized.

    Returns
    -------
    str
        The stripped text.

    """
    return "".join(element.itertext()).replace("\u00a0", " ").strip()


def visible_text_snapshot(tree: etree._ElementTree) -> tuple[str, ...]:
    """Collect normalized heading and paragraph text from a content tree.

    Returns
    -------
    tuple[str, ...]
        One entry per visible text block.

    """
    blocks: list[str] = []
    for node in select_elements(tree, "//text:h | //text:p"):
        text = _visible_node_text(node).replace("\u00a0", " ")
        blocks.append(" ".join(text.split()))
    return tuple(blocks)


def _visible_node_text(node: etree._Element) -> str:
    """Return rendered textual content while excluding accessibility metadata.

    The walk is iterative, so no document depth can exhaust the interpreter's stack.

    Returns
    -------
    str
        Rendered text with graphic accessibility metadata excluded.

    """
    pieces: list[str] = []
    if node.text:
        pieces.append(node.text)
    stack = [(node, iter(node))]
    while stack:
        parent, children = stack[-1]
        child = next(children, None)
        if child is None:
            stack.pop()
            if parent is not node and parent.tail:
                pieces.append(parent.tail)
            continue
        if child.tag in HIDDEN_TAGS:
            if child.tail:
                pieces.append(child.tail)
            continue
        if child.text:
            pieces.append(child.text)
        stack.append((child, iter(child)))
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
