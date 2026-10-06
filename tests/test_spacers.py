# SPDX-License-Identifier: MPL-2.0
"""Regression controls for spacer selection and document-wording preservation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.document_text import text_is_preserved
from odfa11y.namespaces import NS, qn
from odfa11y.odt_package import OdtPackage
from odfa11y.remediate import RemediationOptions, remediate_odt

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("before", "after", "removed", "expected"),
    [
        (("A", "", "B"), ("A", "B"), 1, True),
        (("", "A", "", ""), ("A", ""), 2, True),
        (("A", "B"), ("A",), 1, False),
        (("A", "", "B"), ("A", "changed"), 1, False),
        (("A", "B"), ("B", "A"), 0, False),
        (("A", "B"), ("A", "", "B"), 0, False),
        (("A", "", "B"), ("A", "B"), 0, False),
    ],
)
def test_text_guard_only_allows_counted_empty_block_removal(
    before: tuple[str, ...], after: tuple[str, ...], removed: int, *, expected: bool
) -> None:
    assert text_is_preserved(before, after, removed_empty_blocks=removed) is expected


def test_spacer_removal_preserves_nonempty_paragraphs(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt", add_blank_body_paragraph=True)
    destination = tmp_path / "out.odt"
    result = remediate_odt(
        source, destination, options=RemediationOptions(remove_empty_spacers=True)
    )
    tree = OdtPackage(destination).parse_xml("content.xml")
    assert tree.xpath("//text:p/text()", namespaces=NS) == ["Body paragraph."]
    assert len(tree.xpath("//text:p", namespaces=NS)) == 1
    assert any("Removed 2 empty" in change for change in result.changes)


@pytest.mark.parametrize("marker", ["draw", "bookmark", "tab", "break", "master", "table", "list"])
def test_spacer_removal_retains_semantically_protected_paragraphs(
    tmp_path: Path, marker: str
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt", add_blank_body_paragraph=True)
    package = OdtPackage(source)
    tree = package.parse_xml("content.xml")
    paragraph = tree.xpath("//text:p[not(text())]", namespaces=NS)[0]
    paragraph.set("{http://www.w3.org/XML/1998/namespace}id", "protected")
    if marker in {"table", "list"}:
        namespace, tag = ("table", "table-cell") if marker == "table" else ("text", "list-item")
        parent = paragraph.getparent()
        wrapper = etree.Element(qn(namespace, tag))
        parent.replace(paragraph, wrapper)
        wrapper.append(paragraph)
    elif marker in {"break", "master"}:
        styles = package.parse_xml("styles.xml")
        style = styles.xpath("//style:style[@style:name='Body']", namespaces=NS)[0]
        if marker == "break":
            style.find("style:paragraph-properties", NS).set(qn("fo", "break-before"), "page")
        else:
            style.set(qn("style", "master-page-name"), "Standard")
        package.write_xml("styles.xml", styles)
    else:
        namespace, tag = {
            "draw": ("draw", "frame"),
            "bookmark": ("text", "bookmark"),
            "tab": ("text", "tab"),
        }[marker]
        etree.SubElement(paragraph, qn(namespace, tag))
    package.write_xml("content.xml", tree)
    package.save(source)
    destination = tmp_path / "out.odt"
    remediate_odt(source, destination, options=RemediationOptions(remove_empty_spacers=True))
    output = OdtPackage(destination).parse_xml("content.xml")
    assert len(output.xpath("//*[@xml:id='protected']", namespaces=NS)) == 1
