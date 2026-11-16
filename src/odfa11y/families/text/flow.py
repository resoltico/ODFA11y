# SPDX-License-Identifier: MPL-2.0
"""Extract and compare the visible text of a text document."""

from lxml import etree

from odfa11y.concepts import table_content_fingerprint, visible_words
from odfa11y.families.text.contexts import text_nodes
from odfa11y.families.text.language.styles import language_normalization
from odfa11y.families.text.spacing.edit import spacing_normalization
from odfa11y.odf import names as xml_names
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.odf.styles import normalize_generated

INERT_ATTRIBUTES = {
    xml_names.TEXT_P: frozenset({xml_names.TEXT_STYLE_NAME}),
    xml_names.TEXT_SPAN: frozenset({xml_names.TEXT_STYLE_NAME}),
    xml_names.TEXT_S: frozenset({xml_names.TEXT_C}),
}
# Accessibility metadata, and the image bytes a flat XML document embeds, are not rendered text.
HIDDEN_TAGS = frozenset({xml_names.SVG_TITLE, xml_names.SVG_DESC, xml_names.OFFICE_BINARY_DATA})


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
    for node in text_nodes(tree, xml_names.TEXT_H, xml_names.TEXT_P, xml_names.TABLE_TABLE):
        if any(parent.tag == xml_names.TABLE_TABLE for parent in node.iterancestors()):
            continue
        if node.tag == xml_names.TABLE_TABLE:
            table = (
                normalize_generated(
                    node, language_normalization(document), spacing_normalization(document)
                )
                if document is not None
                else node
            )
            blocks.append("table:" + table_content_fingerprint(table, document))
        else:
            text = visible_words(node)
            blocks.append(" ".join(text.split()))
    return tuple(blocks)
