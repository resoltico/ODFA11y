# SPDX-License-Identifier: MPL-2.0
"""Inspect parsed PDF objects for accessibility diagnostics."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal

from lxml import etree
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from pypdf.generic import BooleanObject, StreamObject
lazy from pypdf.generic import DictionaryObject

from odfa11y.contracts import Description
from odfa11y.errors import ToolFailure
from odfa11y.odf import names as xml_names
from odfa11y.pdf.link_structure import link_annotations
from odfa11y.pdf.reading.consumption import check_consumption
from odfa11y.pdf.reading.limits import check_file_size, check_limits
from odfa11y.pdf.structure_checks import StructureAnalysis, audit_structure
from odfa11y.pdf.structure_walk import pdf_dictionary
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
        structure = _inspect(pdf_path, report)
        return PdfInspection(report, structure)
    except (OSError, PyPdfError, ValueError, KeyError, RecursionError, ToolFailure) as exc:
        report.raise_(rules.PDF000, f"Cannot inspect PDF: {exc}")
    return PdfInspection(report, None)


def audit_pdfua(pdf_path: str | Path) -> Report:
    return inspect_pdf(pdf_path).report


def _inspect(pdf_path: Path, report: Report) -> StructureAnalysis:
    with pdf_path.open("rb") as stream:
        check_file_size(pdf_path)
        reader = PdfReader(stream, strict=True)
        check_limits(pdf_path, len(reader.pages))
        check_consumption(reader)
        structure = _audit_metadata(reader, report)
        analysis = audit_structure(structure, report, link_annotations(reader), reader.pages)
        _audit_content(reader, report, analysis.described_graphics)
        return analysis


def _audit_metadata(reader: PdfReader, report: Report) -> DictionaryObject:
    report.measure(PdfMeasurements(page_count=len(reader.pages)))
    report.measure(PdfMeasurements(format=reader.pdf_header.removeprefix("%")))
    title = (reader.metadata.title or "").strip() if reader.metadata else ""
    if title:
        report.measure(PdfMeasurements(title=title))
    else:
        report.raise_(rules.PDF001, "PDF document title metadata is missing.")
    catalog = reader.root_object
    language = catalog.get("/Lang")
    if isinstance(language, str) and language.strip():
        report.measure(PdfMeasurements(language=language))
    else:
        report.raise_(rules.PDF002, "PDF catalog /Lang is missing.")
    marked = pdf_dictionary(catalog.get("/MarkInfo")).get("/Marked")
    if not isinstance(marked, BooleanObject) or not marked.value:
        report.raise_(rules.PDF003, "PDF is not marked as a tagged document.")
    structure = pdf_dictionary(catalog.get("/StructTreeRoot"))
    if not structure:
        report.raise_(rules.PDF004, "PDF has no /StructTreeRoot.")
    display_title = pdf_dictionary(catalog.get("/ViewerPreferences")).get("/DisplayDocTitle")
    if not isinstance(display_title, BooleanObject) or not display_title.value:
        report.raise_(rules.PDF005, "PDF viewer preferences do not display the title.")
    _audit_xmp(catalog, report)
    return structure


def _audit_xmp(catalog: DictionaryObject, report: Report) -> None:
    metadata = catalog.get("/Metadata")
    if metadata is not None:
        metadata = metadata.get_object()
    part = None
    if isinstance(metadata, StreamObject):
        try:
            root = parse_secure(metadata.get_data())
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
        report.raise_(rules.PDF006, "PDF XMP metadata does not declare PDF/UA-1.")


def _audit_content(reader: PdfReader, report: Report, graphics: int) -> None:
    if not reader.pages:
        report.raise_(rules.PDF009, "PDF contains no pages.")
        return
    text_chars = sum(len(page.extract_text() or "") for page in reader.pages)
    report.measure(PdfMeasurements(text_character_count=text_chars))
    report.measure(PdfMeasurements(described_graphic_count=graphics))
    if not text_chars and not graphics:
        report.raise_(
            rules.PDF010, "No extractable text or inspected described graphical content was found."
        )
