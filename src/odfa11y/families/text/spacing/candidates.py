# SPDX-License-Identifier: MPL-2.0
"""Find empty body paragraphs that may only be visual spacers."""

lazy from lxml import etree

from odfa11y.families.text.contexts import text_nodes
from odfa11y.families.text.flow import is_empty_paragraph
from odfa11y.odf import names as xml_names
from odfa11y.odf import select_elements

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
        for paragraph in text_nodes(tree, xml_names.TEXT_P, main_only=True)
        if is_empty_paragraph(paragraph) and not select_elements(paragraph, PROTECTED_ANCESTORS)
    ]
