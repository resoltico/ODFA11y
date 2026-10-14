# SPDX-License-Identifier: MPL-2.0
"""Native standard roles and link titles keep exporter limitations visible."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest
from lxml import etree

from odfa11y.adapter import Status
from odfa11y.audit import audit_odf
from odfa11y.content import GraphicAlternative, LinkDescription, graphics_fingerprint
from odfa11y.content.links import document_links, link_fingerprint, link_location
from odfa11y.families.text import SetGraphicAlternatives, SetLinkDescriptions
from odfa11y.fidelity import FidelityPolicy, compare_pdfs
from odfa11y.odf import NS, OdfDocument, Part, qn, validate
from odfa11y.pdf import ExportSettings, audit_pdfua, export_pdfua, validate_pdfua

from .native_resource_fixtures import PIXELS, decoded_images, writer_resource

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

pytestmark = pytest.mark.integration


def _mixed_graphics(document: OdfDocument) -> etree._Element:
    """Create an independently described image and an undescribed peer.

    Returns
    -------
    etree._Element
        The peer needing the explicit role decision.

    """
    frame = document.edit(Part.CONTENT).find(".//draw:frame", NS)
    assert frame is not None
    root = document.edit(Part.CONTENT).getroot()
    auto = root.find("office:automatic-styles", NS)
    if auto is None:
        auto = etree.Element(qn("office", "automatic-styles"))
        body = root.find("office:body", NS)
        assert body is not None
        root.insert(root.index(body), auto)
    appearance = etree.SubElement(
        auto,
        qn("style", "style"),
        {qn("style", "name"): "GraphicAppearance", qn("style", "family"): "graphic"},
    )
    etree.SubElement(
        appearance,
        qn("style", "graphic-properties"),
        {qn("draw", "stroke"): "none", qn("draw", "fill"): "none"},
    )
    frame.set(qn("draw", "style-name"), "GraphicAppearance")
    parent = frame.getparent()
    assert parent is not None
    decoration = deepcopy(frame)
    decoration.set(qn("draw", "name"), "Decoration")
    for node in list(decoration):
        if node.tag in {qn("svg", "title"), qn("svg", "desc")}:
            decoration.remove(node)
    parent.append(decoration)
    return decoration


def test_native_mixed_graphic_roles_preserve_content_and_expose_missing_export_support(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    source = writer_resource(tmp_path)
    document = OdfDocument.open(source)
    decoration = _mixed_graphics(document)
    control = document.save(tmp_path / "missing-role.fodt")
    assert "TXT010" in {finding.rule_id for finding in audit_odf(control).findings}
    settings = ExportSettings("writer_pdf_Export", soffice)
    control_pdf = export_pdfua(control, tmp_path / "missing-role.pdf", settings)
    assert "PDF007" in {finding.rule_id for finding in audit_pdfua(control_pdf).findings}
    assert not validate_pdfua(control_pdf, executable=verapdf).compliant
    operation = SetGraphicAlternatives({
        "Decoration": GraphicAlternative(
            decorative=True, fingerprint=graphics_fingerprint(document, [decoration])
        )
    })
    assert operation.apply(document)[0].status == Status.APPLIED
    edited = document.save(tmp_path / "decorative-role.fodt")
    assert validate(document).count == 0
    assert "TXT010" not in {finding.rule_id for finding in audit_odf(edited).findings}
    assert operation.apply(document)[0].status == Status.UNCHANGED
    pdf = export_pdfua(edited, tmp_path / "decorative-role.pdf", settings)
    report = audit_pdfua(pdf)
    validator = validate_pdfua(pdf, executable=verapdf)
    assert report.metadata["extractable_text_characters"] > 0
    assert report.metadata["described_graphics"] >= 1
    assert ((4, 4), PIXELS) in decoded_images(pdf)
    assert compare_pdfs(control_pdf, pdf, FidelityPolicy(raster_tolerance=0.0)).passed
    errors = {finding.rule_id for finding in report.findings if finding.severity == "error"}
    if errors:
        # Standard draw:decorative is ignored by LibreOffice 26.8.1.1. No extension is authored.
        assert errors == {"PDF007"}
        assert not report.passed
        assert not validator.compliant
    else:
        assert report.passed
        assert validator.compliant


def test_native_office_title_and_missing_title_control_measure_actual_exporter(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    source = writer_resource(tmp_path)
    document = OdfDocument.open(source)
    link = document_links(document)[0]
    document.edit(Part.CONTENT)
    link.attrib.pop(qn("office", "name"), None)
    link.attrib.pop(qn("office", "title"), None)
    missing = document.save(tmp_path / "missing-title.fodt")
    settings = ExportSettings("writer_pdf_Export", soffice)
    control_pdf = export_pdfua(missing, tmp_path / "missing-title.pdf", settings)
    assert "PDF019" in {finding.rule_id for finding in audit_pdfua(control_pdf).findings}
    assert not validate_pdfua(control_pdf, executable=verapdf).compliant
    operation = SetLinkDescriptions({
        link_location(link, 1).path: LinkDescription(
            "Read the guide", link_fingerprint(document, link)
        )
    })
    assert operation.apply(document)[0].status == Status.APPLIED
    described = document.save(tmp_path / "link-title.fodt")
    assert validate(document).count == 0
    assert link.get(qn("office", "name")) is None
    assert operation.apply(document)[0].status == Status.UNCHANGED
    pdf = export_pdfua(described, tmp_path / "link-title.pdf", settings)
    report = audit_pdfua(pdf)
    validator = validate_pdfua(pdf, executable=verapdf)
    assert report.metadata["link_annotations"] == 1
    assert compare_pdfs(control_pdf, pdf, FidelityPolicy()).passed
    errors = {finding.rule_id for finding in report.findings if finding.severity == "error"}
    if errors:
        # Writer 26.8.1.1 does not export the normative office:title to PDF /Alt.
        assert errors == {"PDF019"}
        assert not report.passed
        assert not validator.compliant
    else:
        assert report.passed
        assert validator.compliant


def test_native_nested_group_roles_refuse_and_retain_child_alternative_findings(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    document = OdfDocument.open(writer_resource(tmp_path))
    leaf = _mixed_graphics(document)
    parent = leaf.getparent()
    assert parent is not None
    parent.remove(leaf)
    group = etree.SubElement(
        parent,
        qn("draw", "g"),
        {qn("draw", "name"): "Group", qn("draw", "style-name"): "GroupRole"},
    )
    etree.SubElement(group, qn("draw", "g")).append(leaf)
    auto = document.tree(Part.CONTENT).find("office:automatic-styles", NS)
    assert auto is not None
    style = etree.SubElement(
        auto,
        qn("style", "style"),
        {qn("style", "name"): "GroupRole", qn("style", "family"): "graphic"},
    )
    etree.SubElement(style, qn("style", "graphic-properties"), {qn("draw", "decorative"): "true"})
    source = document.save(tmp_path / "nested-group.fodt")
    assert validate(document).count == 0
    assert {"GRAPHIC001", "TXT010"} <= {finding.rule_id for finding in audit_odf(source).findings}
    operation = SetGraphicAlternatives({
        "Group": GraphicAlternative(
            decorative=False, fingerprint=graphics_fingerprint(document, [group])
        )
    })
    before = document.edit_count
    assert operation.apply(document)[0].status == Status.FAILED
    assert document.edit_count == before
    pdf = export_pdfua(
        source, tmp_path / "nested-group.pdf", ExportSettings("writer_pdf_Export", soffice)
    )
    assert "PDF007" in {finding.rule_id for finding in audit_pdfua(pdf).findings}
    assert not validate_pdfua(pdf, executable=verapdf).compliant
