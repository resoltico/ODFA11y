# SPDX-License-Identifier: MPL-2.0
"""Test styles for ODF accessibility workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.odf import NS, OdtPackage, StyleCatalog, qn
from odfa11y.remediation import normalize_paragraph_spacing

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


def test_normalize_spacing_copies_reference_spacing(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    package = OdtPackage(source)
    tree = package.parse_xml("content.xml")
    paragraphs = tree.xpath("//text:p", namespaces=NS)
    paragraphs[0].set(qn("text", "style-name"), "Body")
    paragraphs[-1].set(qn("text", "style-name"), "BodyTight")
    package.write_xml("content.xml", tree)
    package.save(source)

    dest = tmp_path / "normalized.odt"
    normalize_paragraph_spacing(
        source,
        dest,
        reference_text="Body paragraph.",
        target_styles=["BodyTight"],
    )

    out = OdtPackage(dest)
    catalog = StyleCatalog(out)
    out_tree = catalog.content_tree
    target = out_tree.xpath("//text:p[last()]", namespaces=NS)[0]
    new_style = target.get(qn("text", "style-name"))
    assert catalog.spacing_signature(new_style) == catalog.spacing_signature("Body")
