# SPDX-License-Identifier: MPL-2.0
"""The common masked proof rejects undeclared XML changes across every part."""

from pathlib import Path

import pytest
from lxml import etree

from odfa11y.concepts.preservation import ProtectedPackage
from odfa11y.odf import OdfDocument, Part, select_elements
from odfa11y.odf.allowance import Allowance, Attributes, Container, Created, Removed, Text, Wrapped
from odfa11y.odf.canonical import protected_xml
from odfa11y.odf.names import DC_TITLE, OFFICE_META, TEXT_A, TEXT_OUTLINE_LEVEL, TEXT_P
from tests.fixtures.documents import make_flat, make_package


@pytest.mark.parametrize("make", [make_flat, make_package])
def test_only_declared_node_attributes_can_change(tmp_path: Path, make) -> None:
    document = OdfDocument.open(make(tmp_path, "text"))
    paragraph = select_elements(document.tree(Part.CONTENT), "//text:p")[0]
    before = ProtectedPackage.capture(document)
    allowance = Allowance((Attributes(Part.CONTENT, paragraph, frozenset({TEXT_OUTLINE_LEVEL})),))
    paragraph.set(TEXT_OUTLINE_LEVEL, "2")
    assert before.preserved(ProtectedPackage.capture(document), allowance)
    paragraph.text = "Unexpected change outside the declared attribute"
    assert not before.preserved(ProtectedPackage.capture(document), allowance)


def test_other_parts_and_namespace_value_bindings_remain_protected(tmp_path: Path) -> None:
    document = OdfDocument.open(make_package(tmp_path, "text"))
    before = ProtectedPackage.capture(document)
    document.tree(Part.META).getroot().set("unexpected", "value")
    assert not before.preserved(ProtectedPackage.capture(document), Allowance())


def test_created_receipt_does_not_allow_undeclared_content(tmp_path: Path) -> None:
    document = OdfDocument.open(make_flat(tmp_path, "text"))
    before = ProtectedPackage.capture(document)
    meta = select_elements(document.tree(Part.CONTENT), "//office:meta")[0]
    node = etree.SubElement(meta, DC_TITLE)
    node.text = "Title"
    allowance = Allowance((Created.of(Part.META, node),))
    assert before.preserved(ProtectedPackage.capture(document), allowance)
    node.set("unexpected", "value")
    assert not before.preserved(ProtectedPackage.capture(document), allowance)


def test_text_permission_keeps_attributes_and_children_protected(tmp_path: Path) -> None:
    document = OdfDocument.open(make_flat(tmp_path, "text"))
    title = select_elements(document.tree(Part.META), "//dc:title")[0]
    before = ProtectedPackage.capture(document)
    allowance = Allowance((Text(Part.META, title),))
    title.text = "Reviewed"
    assert before.preserved(ProtectedPackage.capture(document), allowance)
    etree.SubElement(title, TEXT_P).text = "Hidden extra content"
    assert not before.preserved(ProtectedPackage.capture(document), allowance)


def test_created_container_is_only_ignored_when_empty_after_masking(tmp_path: Path) -> None:
    document = OdfDocument.open(make_package(tmp_path, "text"))
    before = ProtectedPackage.capture(document)
    root = document.tree(Part.CONTENT).getroot()
    container = etree.SubElement(root, OFFICE_META)
    node = etree.SubElement(container, DC_TITLE)
    node.text = "Title"
    allowance = Allowance((Created.of(Part.CONTENT, node), Container(Part.CONTENT, container)))
    assert before.preserved(ProtectedPackage.capture(document), allowance)
    etree.SubElement(container, TEXT_P).text = "Undeclared sibling"
    assert not before.preserved(ProtectedPackage.capture(document), allowance)


def test_plain_wrapper_retains_all_text(tmp_path: Path) -> None:
    document = OdfDocument.open(make_flat(tmp_path, "text"))
    paragraph = select_elements(document.tree(Part.CONTENT), "//text:p")[0]
    paragraph.text = "Left right"
    before = ProtectedPackage.capture(document)
    paragraph.text = "Left "
    link = etree.SubElement(paragraph, TEXT_A)
    link.text = "right"
    allowance = Allowance((Wrapped(Part.CONTENT, link, protected_xml(link)),))
    assert before.preserved(ProtectedPackage.capture(document), allowance)
    paragraph.text = "Changed "
    assert not before.preserved(ProtectedPackage.capture(document), allowance)


def test_removal_permission_cannot_hide_a_node_that_still_exists(tmp_path: Path) -> None:
    document = OdfDocument.open(make_flat(tmp_path, "text"))
    paragraph = select_elements(document.tree(Part.CONTENT), "//text:p")[0]
    before = ProtectedPackage.capture(document)
    paragraph.text = "Changed instead of removed"
    allowance = Allowance((Removed(Part.CONTENT, paragraph),))
    assert not before.preserved(ProtectedPackage.capture(document), allowance)


def test_creation_permission_cannot_claim_an_existing_node(tmp_path: Path) -> None:
    document = OdfDocument.open(make_flat(tmp_path, "text"))
    paragraph = select_elements(document.tree(Part.CONTENT), "//text:p")[0]
    before = ProtectedPackage.capture(document)
    allowance = Allowance((Created.of(Part.CONTENT, paragraph),))
    assert not before.preserved(ProtectedPackage.capture(document), allowance)
