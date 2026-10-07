# SPDX-License-Identifier: MPL-2.0
"""Read visible ODF words without description metadata or encoded payload bytes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.odf import qn

if TYPE_CHECKING:
    from lxml import etree

HIDDEN = {qn("svg", "title"), qn("svg", "desc"), qn("office", "binary-data")}
SEPARATORS = {qn("text", "s"), qn("text", "tab"), qn("text", "line-break")}


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
