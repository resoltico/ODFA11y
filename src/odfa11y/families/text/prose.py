# SPDX-License-Identifier: MPL-2.0
"""Walk the prose of a paragraph: the text a reader sees, excluding link text and metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.odf import qn

if TYPE_CHECKING:
    from collections.abc import Iterator

    from lxml import etree

#: Content inside these is not prose of the enclosing paragraph: link text is already a
#: link, annotations and graphic descriptions are metadata, and nested paragraphs are
#: walked as paragraphs of their own.
EXCLUDED_TAGS = frozenset({
    qn("text", "a"),
    qn("office", "annotation"),
    qn("svg", "title"),
    qn("svg", "desc"),
    qn("text", "p"),
    qn("text", "h"),
})


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
        descend = isinstance(child.tag, str) and child.tag not in EXCLUDED_TAGS
        if descend and child.text:
            yield child, "text"
        if descend:
            stack.append((child, iter(child)))
        elif child.tail:
            yield child, "tail"
