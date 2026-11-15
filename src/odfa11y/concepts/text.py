# SPDX-License-Identifier: MPL-2.0
"""Read visible ODF words without description metadata or encoded payload bytes."""

lazy from lxml import etree

from odfa11y.concepts.locations import page_location, sheet_location
from odfa11y.odf import NS, qn
from odfa11y.odf import names as xml_names

HIDDEN = {xml_names.SVG_TITLE, xml_names.SVG_DESC, xml_names.OFFICE_BINARY_DATA}
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
    xml_names.OFFICE_ANNOTATION,
    xml_names.TEXT_TRACKED_CHANGES,
    xml_names.TEXT_HIDDEN_TEXT,
    xml_names.TEXT_CONDITIONAL_TEXT,
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
        if ancestor.tag in {xml_names.TEXT_P, xml_names.TEXT_H} and _conditional_paragraph(
            ancestor
        ):
            return False
        if ancestor.tag == xml_names.TEXT_SECTION and (
            ancestor.get(xml_names.TEXT_CONDITION) is not None
            or ancestor.get(xml_names.TEXT_DISPLAY) in {"none", "condition"}
        ):
            return False
        if main_only and ancestor.tag in {xml_names.TEXT_NOTE, xml_names.DRAW_TEXT_BOX}:
            return False
    return True


def _conditional_paragraph(block: etree._Element) -> bool:
    for marker in block.iter(xml_names.TEXT_HIDDEN_PARAGRAPH):
        owner = next(marker.iterancestors(xml_names.TEXT_P, xml_names.TEXT_H), None)
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
        if parent.tag in {xml_names.TEXT_NOTE, xml_names.DRAW_TEXT_BOX}:
            kind = "note" if parent.tag == xml_names.TEXT_NOTE else "text-box"
            peers = [
                peer
                for body in parent.getroottree().getroot().findall("office:body", NS)
                for peer in body.iter(str(parent.tag))
                if eligible_text_node(peer)
            ]
            return f"content/{kind}[{peers.index(parent) + 1}]" if parent in peers else "content"
        if parent.tag == xml_names.DRAW_PAGE and container is not None:
            peers = list(container.iterchildren(xml_names.DRAW_PAGE))
            return page_location(parent, peers.index(parent) + 1).path
        if (
            parent.tag == xml_names.TABLE_TABLE
            and container is not None
            and container.tag == xml_names.OFFICE_SPREADSHEET
        ):
            peers = list(container.iterchildren(xml_names.TABLE_TABLE))
            return sheet_location(peers.index(parent) + 1).path
    return "content"
