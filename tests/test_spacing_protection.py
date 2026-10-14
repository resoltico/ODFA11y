# SPDX-License-Identifier: MPL-2.0
"""Generated spacing must not mask changes to excluded authored contexts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.adapter import Status
from odfa11y.families.text import NormalizeSpacing
from odfa11y.families.text.protection import ProtectedEdit
from odfa11y.families.text.spacing import derived_style_name
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.remediation import remediate

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


def test_proven_spacing_derivation_does_not_mask_annotation_style_change(tmp_path: Path) -> None:
    document = OdfDocument.open(make_minimal_odt(tmp_path / "source.odt"))
    paragraph = select_elements(document.tree(Part.CONTENT), "//text:p")[0]
    annotation = etree.SubElement(paragraph, qn("office", "annotation"))
    authored = etree.SubElement(annotation, qn("text", "p"))
    authored.set(qn("text", "style-name"), "Body")
    authored.text = "Protected annotation"
    operation = NormalizeSpacing("Synthetic heading", ("Body",))
    guard = ProtectedEdit(document, operation)
    assert operation.apply(document)[0].status is Status.APPLIED
    assert guard.intact()
    authored.set(qn("text", "style-name"), derived_style_name("Body"))
    assert not guard.intact()


def test_spacing_refuses_shared_generated_style_in_excluded_content(tmp_path: Path) -> None:
    document = OdfDocument.open(make_minimal_odt(tmp_path / "source.odt"))
    operation = NormalizeSpacing("Synthetic heading", ("Body",))
    assert operation.apply(document)[0].status is Status.APPLIED
    paragraph = select_elements(document.tree(Part.CONTENT), "//text:p")[0]
    annotation = etree.SubElement(paragraph, qn("office", "annotation"))
    authored = etree.SubElement(annotation, qn("text", "p"))
    authored.set(qn("text", "style-name"), derived_style_name("Body"))
    authored.text = "Protected annotation"
    reference = select_elements(
        document.tree(Part.STYLES),
        "//style:style[@style:name='Heading1']/style:paragraph-properties",
    )[0]
    reference.set(qn("fo", "margin-bottom"), "2cm")
    before = etree.tostring(document.tree(Part.CONTENT))
    outcomes = operation.apply(document)
    assert outcomes[0].status is Status.FAILED
    assert "excluded content" in outcomes[0].message
    assert etree.tostring(document.tree(Part.CONTENT)) == before


def test_spacing_in_table_cells_uses_only_proven_derivations_and_reapplies(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt", features={"with_data_table": True})
    operation = NormalizeSpacing("Synthetic heading", ("(none)",))
    output = tmp_path / "reviewed.odt"
    assert remediate(source, output, [operation]).changed
    assert not remediate(output, tmp_path / "again.odt", [operation]).changed
    before = select_elements(
        OdfDocument.open(source).tree(Part.CONTENT), "//table:table-cell/text:p"
    )
    after = select_elements(
        OdfDocument.open(output).tree(Part.CONTENT), "//table:table-cell/text:p"
    )
    assert [node.text for node in before] == [node.text for node in after]
    assert all(node.get(qn("text", "style-name")) == derived_style_name("(none)") for node in after)


def test_text_only_paragraph_base_derives_valid_ordered_spacing_properties(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    document = OdfDocument.open(source)
    body = select_elements(document.edit(Part.STYLES), "//style:style[@style:name='Body']")[0]
    props = body.find(qn("style", "paragraph-properties"))
    assert props is not None
    body.remove(props)
    text = etree.SubElement(body, qn("style", "text-properties"))
    text.set(qn("fo", "font-size"), "12pt")
    assert validate(document).count == 0
    document.save(source)
    output = tmp_path / "reviewed.odt"
    operation = NormalizeSpacing("Synthetic heading", ("Body",))
    assert remediate(source, output, [operation]).changed
    after = OdfDocument.open(output)
    assert validate(after).count == 0
    derived = select_elements(after.tree(Part.CONTENT), "//style:style")[0]
    assert [node.tag for node in derived] == [
        qn("style", "paragraph-properties"),
        qn("style", "text-properties"),
    ]
    assert not remediate(output, tmp_path / "again.odt", [operation]).changed
