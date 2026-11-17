# SPDX-License-Identifier: AGPL-3.0-only
"""Walk the prose of a paragraph: the text a reader sees, excluding link text and metadata."""

lazy from collections.abc import Iterator

lazy from lxml import etree

from odfa11y.concepts import eligible_text_node
from odfa11y.odf import names as xml_names

# Only text spans extend a paragraph's address prose. Nested contexts are walked as
# blocks of their own; authored fields and visibility/revision declarations stay exact.


def prose_slots(block: etree._Element) -> Iterator[tuple[etree._Element, str]]:
    """Yield each text slot of a paragraph's prose in document order.

    A slot is an element's ``text`` or ``tail``. The tail of an excluded element is prose of
    the enclosing paragraph and is yielded; the excluded element's own content is not.

    Yields
    ------
    tuple[etree._Element, str]
        The owner and ``"text"`` or ``"tail"``; the owner may be a comment for a tail.

    """
    if block.text:
        yield block, "text"
    stack = [(block, iter(block))]
    while stack:
        parent, children = stack[-1]
        child = next(children, None)
        if child is None:
            stack.pop()
            if parent is not block and parent.tail:
                yield parent, "tail"
            continue
        descend = child.tag == xml_names.TEXT_SPAN and eligible_text_node(child)
        if descend and child.text:
            yield child, "text"
        if descend:
            stack.append((child, iter(child)))
        elif child.tail:
            yield child, "tail"


def address_wrapper_scope(node: etree._Element) -> bool:
    """Whether a new wrapper belongs to the exact prose vocabulary we may linkify.

    Returns
    -------
    bool
        True for current-flow paragraph/heading text through text:span wrappers only.

    """
    parent = node.getparent()
    while parent is not None and parent.tag == xml_names.TEXT_SPAN:
        parent = parent.getparent()
    return (
        parent is not None
        and parent.tag in {xml_names.TEXT_P, xml_names.TEXT_H}
        and eligible_text_node(node)
    )
