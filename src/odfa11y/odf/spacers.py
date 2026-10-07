# SPDX-License-Identifier: MPL-2.0
"""Find empty body paragraphs that may only be visual spacers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .text import is_empty_paragraph
from .xpath import select_elements

if TYPE_CHECKING:
    from lxml import etree

PROTECTED_ANCESTORS = (
    "ancestor::table:table-cell | ancestor::draw:text-box | "
    "ancestor::office:annotation | ancestor::text:list-item"
)


def spacer_candidates(tree: etree._ElementTree) -> list[etree._Element]:
    """Select empty body paragraphs outside cells, text boxes, annotations and lists.

    Audit and remediation share this definition, so a finding is always one the
    remediation could act on (before its further check for page-break styles).

    Returns
    -------
    list[etree._Element]
        The empty, unprotected paragraphs in document order.

    """
    return [
        paragraph
        for paragraph in select_elements(tree, "//text:p")
        if is_empty_paragraph(paragraph) and not select_elements(paragraph, PROTECTED_ANCESTORS)
    ]
