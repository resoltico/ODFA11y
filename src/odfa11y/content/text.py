# SPDX-License-Identifier: MPL-2.0
"""Read visible ODF words without description metadata or encoded payload bytes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.odf import NS, qn

from .locations import page_location, sheet_location

if TYPE_CHECKING:
    from lxml import etree

HIDDEN = {qn("svg", "title"), qn("svg", "desc"), qn("office", "binary-data")}
SEPARATORS = {qn("text", name) for name in ("s", "tab", "line-break", "p", "h")}


def visible_words(element: etree._Element) -> str:
    """Read normalized words, including explicit ODF word separators.

    Returns
    -------
    str
        Visible wording; repeated spaces have one word boundary and are never expanded.

    """
    pieces = [element.text or ""]
    stack = [(element, iter(element))]
    while stack:
        parent, children = stack[-1]
        child = next(children, None)
        if child is None:
            stack.pop()
            if parent is not element and parent.tail:
                pieces.append(parent.tail)
            continue
        if child.tag in HIDDEN:
            if child.tail:
                pieces.append(child.tail)
            continue
        if child.tag in SEPARATORS:
            pieces.append(" ")
        if child.text:
            pieces.append(child.text)
        stack.append((child, iter(child)))
    return " ".join("".join(pieces).replace("\u00a0", " ").split())


TEXT_EXCLUDED_CONTEXTS = frozenset({
    qn("office", "annotation"),
    qn("text", "tracked-changes"),
    qn("text", "hidden-text"),
    qn("text", "conditional-text"),
})


def eligible_text_node(node: etree._Element, *, main_only: bool = False) -> bool:
    """Whether a node belongs to established current text flow.

    Returns
    -------
    bool
        False for annotation/history/conditional branches, and optionally notes/text boxes.

    """
    for ancestor in (node, *node.iterancestors()):
        tag = str(ancestor.tag)
        if tag.startswith("{") and tag.split("}", 1)[0][1:] not in NS.values():
            return False
        if ancestor.tag in TEXT_EXCLUDED_CONTEXTS:
            return False
        if ancestor.tag in {qn("text", "p"), qn("text", "h")} and _conditional_paragraph(ancestor):
            return False
        if ancestor.tag == qn("text", "section") and (
            ancestor.get(qn("text", "condition")) is not None
            or ancestor.get(qn("text", "display")) in {"none", "condition"}
        ):
            return False
        if main_only and ancestor.tag in {qn("text", "note"), qn("draw", "text-box")}:
            return False
    return True


def _conditional_paragraph(block: etree._Element) -> bool:
    for marker in block.iter(qn("text", "hidden-paragraph")):
        owner = next(marker.iterancestors(qn("text", "p"), qn("text", "h")), None)
        if owner is block:
            return True
    return False


def reading_context_path(node: etree._Element) -> str:
    """Qualify a source target by its enclosing current-flow note or text box.

    Returns
    -------
    str
        The enclosing logical context; main body retains content.

    """
    for parent in node.iterancestors():
        container = parent.getparent()
        if parent.tag in {qn("text", "note"), qn("draw", "text-box")}:
            kind = "note" if parent.tag == qn("text", "note") else "text-box"
            peers = [
                peer
                for body in parent.getroottree().getroot().findall("office:body", NS)
                for peer in body.iter(str(parent.tag))
                if eligible_text_node(peer)
            ]
            return f"content/{kind}[{peers.index(parent) + 1}]" if parent in peers else "content"
        if parent.tag == qn("draw", "page") and container is not None:
            peers = list(container.iterchildren(qn("draw", "page")))
            return page_location(parent, peers.index(parent) + 1).path
        if (
            parent.tag == qn("table", "table")
            and container is not None
            and container.tag == qn("office", "spreadsheet")
        ):
            peers = list(container.iterchildren(qn("table", "table")))
            return sheet_location(peers.index(parent) + 1).path
    return "content"
