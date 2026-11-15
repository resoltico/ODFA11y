# SPDX-License-Identifier: MPL-2.0
"""Shared native graphic, hyperlink and page target domains."""

from collections.abc import Iterator

from lxml import etree

from odfa11y.concepts.graphic_identity import SHAPE_TAGS, GraphicIdentity
from odfa11y.concepts.links import document_links, link_fingerprint, link_location
from odfa11y.concepts.pages import page_fingerprint, page_location, pages
from odfa11y.concepts.text import eligible_text_node
from odfa11y.decisions.domain import TargetDomain
from odfa11y.odf import Family, OdfDocument, Part, select_elements
from odfa11y.odf import names as xml_names
from odfa11y.targets import Fingerprint, TargetPath


def graphic_nodes(document: OdfDocument) -> list[etree._Element]:
    if document.kind and document.kind.family is Family.IMAGE:
        return select_elements(document.tree(Part.CONTENT), "//office:body/office:image/draw:frame")
    return [
        node
        for node in select_elements(document.tree(Part.CONTENT), "//office:body//*")
        if node.tag in SHAPE_TAGS and node.tag != xml_names.DRAW_G and eligible_text_node(node)
    ]


def _graphics(document: OdfDocument) -> Iterator[tuple[TargetPath, etree._Element]]:
    nodes = graphic_nodes(document)
    identity = GraphicIdentity(document, nodes)
    for node in nodes:
        yield TargetPath(identity.target(node)), node


def _graphic_fingerprint(document: OdfDocument, node: etree._Element) -> Fingerprint:
    identity = GraphicIdentity(document, graphic_nodes(document))
    return identity.fingerprint(identity.matching(identity.target(node)))


def _links(document: OdfDocument) -> Iterator[tuple[TargetPath, etree._Element]]:
    for index, node in enumerate(document_links(document), 1):
        yield link_location(node, index).path, node


def _pages(document: OdfDocument) -> Iterator[tuple[TargetPath, etree._Element]]:
    for index, node in enumerate(pages(document), 1):
        yield page_location(node, index).path, node


def _page_fingerprint(document: OdfDocument, node: etree._Element) -> Fingerprint:
    return page_fingerprint(node, document)


GRAPHICS = TargetDomain(_graphics, _graphic_fingerprint)
LINKS = TargetDomain(_links, link_fingerprint)
PAGES = TargetDomain(_pages, _page_fingerprint)
