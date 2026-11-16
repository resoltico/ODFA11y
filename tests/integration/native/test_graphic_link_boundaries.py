# SPDX-License-Identifier: MPL-2.0
"""Native standard roles and link titles keep exporter limitations visible."""

from copy import deepcopy
lazy from collections.abc import Callable
lazy from pathlib import Path

from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.audit.validation import validate_pdfua
from odfa11y.concepts import graphics_fingerprint
from odfa11y.concepts.links import document_links, link_fingerprint, link_location
from odfa11y.decisions.edit import Status
from odfa11y.native.libreoffice import ExportSettings, export_pdfua
from odfa11y.odf import NS, OdfDocument, Part, qn, validate
from odfa11y.pdf import audit_pdfua
from odfa11y.pdf.audit import PdfMeasurements
from odfa11y.pdf.fidelity import compare_pdfs
from odfa11y.pdf.structure.links import PdfLinkMeasurements
from odfa11y.plans.fidelity import Pagination
from odfa11y.rules import registry as rules
from tests.fixtures.answers import (
    apply_in_memory,
    graphic_answer,
    graphic_inputs,
    link_answer,
    link_inputs,
)
from tests.fixtures.measurements import measured, measurement
from tests.fixtures.native_resources import PIXELS, decoded_images, writer_resource


def _mixed_graphics(document: OdfDocument) -> etree._Element:
    """Create an independently described image and an undescribed peer.

    Returns
    -------
    etree._Element
        The peer needing the explicit role decision.

    """
    frame = document.tree(Part.CONTENT).find(".//draw:frame", NS)
    assert frame is not None
    root = document.tree(Part.CONTENT).getroot()
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
    assert rules.GRAPHIC001.id in {finding.rule_id for finding in audit_odf(control).findings}
    settings = ExportSettings("writer_pdf_Export", soffice)
    control_pdf = export_pdfua(control, tmp_path / "missing-role.pdf", settings)
    assert rules.PDF008.id in {finding.rule_id for finding in audit_pdfua(control_pdf).findings}
    assert not validate_pdfua(control_pdf, executable=verapdf).compliant
    operation = graphic_inputs({
        "Decoration": graphic_answer(
            decorative=True, fingerprint=graphics_fingerprint(document, [decoration])
        )
    })
    assert apply_in_memory(document, operation)[0].status == Status.APPLIED
    edited = document.save(tmp_path / "decorative-role.fodt")
    assert validate(document).count == 0
    assert rules.GRAPHIC001.id not in {finding.rule_id for finding in audit_odf(edited).findings}
    assert apply_in_memory(document, operation)[0].status == Status.UNCHANGED
    pdf = export_pdfua(edited, tmp_path / "decorative-role.pdf", settings)
    report = audit_pdfua(pdf)
    validator = validate_pdfua(pdf, executable=verapdf)
    assert measured(measurement(report, PdfMeasurements).text_character_count) > 0
    assert measured(measurement(report, PdfMeasurements).described_graphic_count) >= 1
    assert ((4, 4), PIXELS) in decoded_images(pdf)
    assert compare_pdfs(control_pdf, pdf, Pagination.SAME(raster_tolerance=0.0)).error_count == 0
    errors = {finding.rule_id for finding in report.findings if finding.severity == "error"}
    if errors:
        # Standard draw:decorative is ignored by LibreOffice 26.8.1.1. No extension is authored.
        assert errors == {rules.PDF008.id}
        assert report.error_count != 0
        assert not validator.compliant
    else:
        assert report.error_count == 0
        assert validator.compliant


def test_native_office_title_and_missing_title_control_measure_actual_exporter(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    source = writer_resource(tmp_path)
    document = OdfDocument.open(source)
    link = document_links(document)[0]
    document.tree(Part.CONTENT)
    link.attrib.pop(qn("office", "name"), None)
    link.attrib.pop(qn("office", "title"), None)
    missing = document.save(tmp_path / "missing-title.fodt")
    settings = ExportSettings("writer_pdf_Export", soffice)
    control_pdf = export_pdfua(missing, tmp_path / "missing-title.pdf", settings)
    assert rules.PDF020.id in {finding.rule_id for finding in audit_pdfua(control_pdf).findings}
    assert not validate_pdfua(control_pdf, executable=verapdf).compliant
    operation = link_inputs({
        link_location(link, 1).path: link_answer("Read the guide", link_fingerprint(document, link))
    })
    assert apply_in_memory(document, operation)[0].status == Status.APPLIED
    described = document.save(tmp_path / "link-title.fodt")
    assert validate(document).count == 0
    assert link.get(qn("office", "name")) is None
    assert apply_in_memory(document, operation)[0].status == Status.UNCHANGED
    pdf = export_pdfua(described, tmp_path / "link-title.pdf", settings)
    report = audit_pdfua(pdf)
    validator = validate_pdfua(pdf, executable=verapdf)
    assert measured(measurement(report, PdfLinkMeasurements).link_annotation_count) == 1
    assert compare_pdfs(control_pdf, pdf, Pagination.SAME()).error_count == 0
    errors = {finding.rule_id for finding in report.findings if finding.severity == "error"}
    if errors:
        # Writer 26.8.1.1 does not export the normative office:title to PDF /Alt.
        assert errors == {rules.PDF020.id}
        assert report.error_count != 0
        assert not validator.compliant
    else:
        assert report.error_count == 0
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
    assert {rules.GRAPHIC003.id, rules.GRAPHIC001.id} <= {
        finding.rule_id for finding in audit_odf(source).findings
    }
    operation = graphic_inputs({
        "Group": graphic_answer(
            decorative=False, fingerprint=graphics_fingerprint(document, [group])
        )
    })
    before = document.checkpoint()
    assert apply_in_memory(document, operation)[0].status == Status.FAILED
    assert not document.changed_since(before)
    pdf = export_pdfua(
        source, tmp_path / "nested-group.pdf", ExportSettings("writer_pdf_Export", soffice)
    )
    assert rules.PDF008.id in {finding.rule_id for finding in audit_pdfua(pdf).findings}
    assert not validate_pdfua(pdf, executable=verapdf).compliant
