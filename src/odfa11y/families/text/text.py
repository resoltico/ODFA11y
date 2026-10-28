# SPDX-License-Identifier: MPL-2.0
"""Extract and compare the visible text of a text document."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument

from odfa11y.content import table_content_fingerprint, visible_words
from odfa11y.odf import qn

from .contexts import text_nodes
from .spacing import normalized_spacing_tree

INERT_ATTRIBUTES = {
    qn("text", "p"): frozenset({qn("text", "style-name")}),
    qn("text", "span"): frozenset({qn("text", "style-name")}),
    qn("text", "s"): frozenset({qn("text", "c")}),
}
# Accessibility metadata, and the image bytes a flat XML document embeds, are not rendered text.
HIDDEN_TAGS = frozenset({qn("svg", "title"), qn("svg", "desc"), qn("office", "binary-data")})


def is_empty_paragraph(p: etree._Element) -> bool:
    """Whether a paragraph has no text and nothing but inert inline elements.

    Anything else (a frame, bookmark, tab, field, change marker, index entry, ...) means the
    paragraph may carry meaning, so it is not a spacer; only an allow-list of inert elements
    counts as empty. Attributes also carry identities, RDF metadata and conditional or
    layered style references; only the ordinary style reference and space count are inert.

    Returns
    -------
    bool
        True when the paragraph is empty.

    """
    if visible_words(p).strip():
        return False
    return all(
        (allowed := INERT_ATTRIBUTES.get(str(node.tag))) is not None and set(node.attrib) <= allowed
        for node in p.iter()
    )


def visible_text_snapshot(
    tree: etree._ElementTree, document: OdfDocument | None = None
) -> tuple[str, ...]:
    """Collect normalized heading and paragraph text from a content tree.

    Returns
    -------
    tuple[str, ...]
        One entry per visible text block.

    """
    blocks: list[str] = []
    for node in text_nodes(tree, qn("text", "h"), qn("text", "p"), qn("table", "table")):
        if any(parent.tag == qn("table", "table") for parent in node.iterancestors()):
            continue
        if node.tag == qn("table", "table"):
            table = normalized_spacing_tree(document, node) if document is not None else node
            blocks.append("table:" + table_content_fingerprint(table, document))
        else:
            text = visible_words(node)
            blocks.append(" ".join(text.split()))
    return tuple(blocks)


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
