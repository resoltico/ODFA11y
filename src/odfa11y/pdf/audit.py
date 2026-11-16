# SPDX-License-Identifier: AGPL-3.0-only
"""Inspect parsed PDF objects for accessibility diagnostics."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal

from lxml import etree
from pypdf.errors import PyPdfError
from pypdf.generic import BooleanObject, StreamObject
lazy from pypdf.generic import DictionaryObject

from odfa11y.contracts import Description
from odfa11y.errors import ToolFailure
from odfa11y.odf import names as xml_names
from odfa11y.pdf.reading import BoundedPdf, open_pdf
from odfa11y.pdf.reading.objects import dictionary
from odfa11y.pdf.structure.checks import StructureAnalysis, audit_structure
from odfa11y.pdf.structure.fonts import Font, read_fonts
from odfa11y.pdf.structure.links import link_annotations
from odfa11y.report import Report
from odfa11y.report.model import ReportKind
from odfa11y.rules import registry as rules
from odfa11y.safe_xml import parse_secure

PDFUA_PART = xml_names.PDFUA_PART


@dataclass(frozen=True, slots=True)
class PdfMeasurements:
    """Measurements produced by pdf-document analysis; None denotes unmeasured data."""

    producer: Literal["pdf-document"] = field(default="pdf-document", init=False)
    page_count: Annotated[int | None, Description("Pages in the inspected PDF.")] = None
    format: Annotated[str | None, Description("PDF header format declaration.")] = None
    text_character_count: Annotated[int | None, Description("Extractable text characters.")] = None
    described_graphic_count: Annotated[
        int | None, Description("Inspected graphical content with descriptions.")
    ] = None
    title: Annotated[str | None, Description("PDF document title.")] = None
    language: Annotated[str | None, Description("PDF catalog language.")] = None
    ua_part: Annotated[int | None, Description("Declared PDF/UA part.")] = None


@dataclass(frozen=True, slots=True)
class PdfInspection:
    report: Report
    structure: StructureAnalysis | None
    fonts: tuple[Font, ...] | None = None
    link_descriptions: tuple[str, ...] = ()
    image_operations: int = 0
    artifact_image_operations: int = 0


def inspect_pdf(pdf_path: str | Path) -> PdfInspection:
    """Inspect PDF accessibility markers without claiming full conformance.

    Returns
    -------
    Report
        Structural accessibility findings and PDF metadata.

    """
    pdf_path = Path(pdf_path)
    report = Report(kind=ReportKind.PDF, subject=str(pdf_path), _sources=(pdf_path,))
    try:
        return _inspect(pdf_path, report)
    except (OSError, PyPdfError, ValueError, KeyError, RecursionError, ToolFailure) as exc:
        report.raise_(rules.PDF001, f"Cannot inspect PDF: {exc}")
    return PdfInspection(report, None)


def audit_pdfua(pdf_path: str | Path) -> Report:
    return inspect_pdf(pdf_path).report


def _inspect(pdf_path: Path, report: Report) -> PdfInspection:
    with open_pdf(pdf_path) as pdf:
        _audit_metadata(pdf, report)
        annotations = link_annotations(pdf)
        analysis = audit_structure(pdf.structure, report, annotations, pdf.contents)
        _audit_content(pdf, report, analysis.described_graphics)
        descriptions = [item.description for item in annotations if item.description is not None]
        descriptions += [
            value
            for node in pdf.structure.walk()
            if node.role == "Link" and isinstance((value := node.element.get("/Alt")), str)
        ]
        scans = [scan for page in pdf.contents for _, scan in page.scopes]
        return PdfInspection(
            report,
            analysis,
            read_fonts(pdf),
            tuple(descriptions),
            sum(scan.image_operations for scan in scans),
            sum(scan.artifact_image_operations for scan in scans),
        )


def _audit_metadata(reader: BoundedPdf, report: Report) -> DictionaryObject:
    report.measure(PdfMeasurements(page_count=len(reader.pages)))
    report.measure(PdfMeasurements(format=reader.header.removeprefix("%")))
    title = (reader.metadata.title or "").strip() if reader.metadata else ""
    if title:
        report.measure(PdfMeasurements(title=title))
    else:
        report.raise_(rules.PDF002, "PDF document title metadata is missing.")
    catalog = reader.catalog
    language = catalog.get("/Lang")
    if isinstance(language, str) and language.strip():
        report.measure(PdfMeasurements(language=language))
    else:
        report.raise_(rules.PDF003, "PDF catalog /Lang is missing.")
    marked = dictionary(catalog.get("/MarkInfo")).get("/Marked")
    if not isinstance(marked, BooleanObject) or not marked.value:
        report.raise_(rules.PDF004, "PDF is not marked as a tagged document.")
    structure = dictionary(catalog.get("/StructTreeRoot"))
    if not structure:
        report.raise_(rules.PDF005, "PDF has no /StructTreeRoot.")
    display_title = dictionary(catalog.get("/ViewerPreferences")).get("/DisplayDocTitle")
    if not isinstance(display_title, BooleanObject) or not display_title.value:
        report.raise_(rules.PDF006, "PDF viewer preferences do not display the title.")
    _audit_xmp(reader, report)
    return structure


def _audit_xmp(reader: BoundedPdf, report: Report) -> None:
    metadata = reader.catalog.get("/Metadata")
    if metadata is not None:
        metadata = metadata.get_object()
    part = None
    if isinstance(metadata, StreamObject):
        try:
            root = parse_secure(reader.data(metadata))
            part = next(
                (
                    node.text or node.get(PDFUA_PART)
                    for node in root.iter()
                    if node.tag == PDFUA_PART or PDFUA_PART in node.attrib
                ),
                None,
            )
        except etree.XMLSyntaxError:
            part = None
    if part and part.strip() == "1":
        report.measure(PdfMeasurements(ua_part=1))
    else:
        report.raise_(rules.PDF007, "PDF XMP metadata does not declare PDF/UA-1.")


def _audit_content(reader: BoundedPdf, report: Report, graphics: int) -> None:
    if not reader.pages:
        report.raise_(rules.PDF010, "PDF contains no pages.")
        return
    text_chars = sum(len(reader.text(index)) for index in range(len(reader.pages)))
    report.measure(PdfMeasurements(text_character_count=text_chars))
    report.measure(PdfMeasurements(described_graphic_count=graphics))
    if not text_chars and not graphics:
        report.raise_(
            rules.PDF011, "No extractable text or inspected described graphical content was found."
        )
