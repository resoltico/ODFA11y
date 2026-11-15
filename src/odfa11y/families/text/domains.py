# SPDX-License-Identifier: MPL-2.0
"""Writer heading, table and language target identities."""

from collections.abc import Iterator

from lxml import etree

from odfa11y.concepts.table_identity import table_fingerprint
from odfa11y.concepts.text import visible_words
from odfa11y.decisions.domain import TargetDomain
from odfa11y.families.text.contexts import context_location, text_nodes
from odfa11y.families.text.headings.edit import heading_fingerprint, heading_location
from odfa11y.families.text.language.effective import language_targets
from odfa11y.families.text.language.operations import language_fingerprint
from odfa11y.odf import OdfDocument, Part
from odfa11y.odf import names as xml_names
from odfa11y.targets import Fingerprint, TargetPath


def _headings(document: OdfDocument) -> Iterator[tuple[TargetPath, etree._Element]]:
    for index, node in enumerate(
        text_nodes(document.tree(Part.CONTENT), xml_names.TEXT_H, main_only=True), 1
    ):
        yield heading_location(node, index).path, node


def _heading_fingerprint(document: OdfDocument, node: etree._Element) -> Fingerprint:
    return heading_fingerprint(node, document)


def _tables(document: OdfDocument) -> Iterator[tuple[TargetPath, etree._Element]]:
    for index, node in enumerate(text_nodes(document.tree(Part.CONTENT), xml_names.TABLE_TABLE), 1):
        yield context_location(node, "table", index, node.get(xml_names.TABLE_NAME)).path, node


def _table_fingerprint(document: OdfDocument, node: etree._Element) -> Fingerprint:
    return Fingerprint(table_fingerprint(node, document))


def _languages(document: OdfDocument) -> Iterator[tuple[TargetPath, etree._Element]]:
    for path, node in language_targets(document).items():
        if visible_words(node):
            yield TargetPath(path), node


HEADINGS = TargetDomain(_headings, _heading_fingerprint)
TABLES = TargetDomain(_tables, _table_fingerprint)
LANGUAGES = TargetDomain(_languages, language_fingerprint)
