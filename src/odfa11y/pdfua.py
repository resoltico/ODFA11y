# SPDX-License-Identifier: MPL-2.0
"""Inspect parsed PDF objects for accessibility diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from lxml import etree
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from pypdf.generic import BooleanObject, StreamObject

from .models import AuditReport, Severity
from .odt_package import secure_xml_parser
from .pdf_export import export_pdfua, run_verapdf
from .pdf_structure import audit_structure, pdf_dictionary

if TYPE_CHECKING:
    from pypdf import PageObject
    from pypdf.generic import DictionaryObject

__all__ = ["audit_pdfua", "export_pdfua", "run_verapdf"]
PDFUA_PART = "{http://www.aiim.org/pdfua/ns/id/}part"


def audit_pdfua(pdf_path: str | Path) -> AuditReport:
    """Inspect PDF accessibility markers without claiming full conformance.

    Returns
    -------
    AuditReport
        Structural accessibility findings and PDF metadata.

    """
    pdf_path = Path(pdf_path)
    report = AuditReport(subject=str(pdf_path))
    try:
        with pdf_path.open("rb") as stream:
            reader = PdfReader(stream, strict=True)
            structure = _audit_metadata(reader, report)
            audit_structure(structure, report)
            _audit_content(reader, report)
    except (OSError, PyPdfError, ValueError, KeyError) as exc:
        report.add("PDF000", Severity.ERROR, f"Cannot inspect PDF: {exc}", location=str(pdf_path))
    return report


def _audit_metadata(reader: PdfReader, report: AuditReport) -> DictionaryObject:
    report.metadata["pages"] = len(reader.pages)
    report.metadata["pdf_format"] = reader.pdf_header.removeprefix("%")
    title = (reader.metadata.title or "").strip() if reader.metadata else ""
    if title:
        report.metadata["title"] = title
    else:
        report.add("PDF001", Severity.ERROR, "PDF document title metadata is missing.")
    catalog = reader.root_object
    language = catalog.get("/Lang")
    if isinstance(language, str) and language.strip():
        report.metadata["language"] = language
    else:
        report.add("PDF002", Severity.ERROR, "PDF catalog /Lang is missing.")
    marked = pdf_dictionary(catalog.get("/MarkInfo")).get("/Marked")
    if not isinstance(marked, BooleanObject) or not marked.value:
        report.add("PDF003", Severity.ERROR, "PDF is not marked as a tagged document.")
    structure = pdf_dictionary(catalog.get("/StructTreeRoot"))
    if not structure:
        report.add("PDF004", Severity.ERROR, "PDF has no /StructTreeRoot.")
    display_title = pdf_dictionary(catalog.get("/ViewerPreferences")).get("/DisplayDocTitle")
    if not isinstance(display_title, BooleanObject) or not display_title.value:
        report.add("PDF005", Severity.WARNING, "PDF viewer preferences do not display the title.")
    _audit_xmp(catalog, report)
    return structure


def _audit_xmp(catalog: DictionaryObject, report: AuditReport) -> None:
    metadata = catalog.get("/Metadata")
    if metadata is not None:
        metadata = metadata.get_object()
    part = None
    if isinstance(metadata, StreamObject):
        try:
            root = etree.fromstring(metadata.get_data(), parser=secure_xml_parser())
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
        report.metadata["pdfua_part"] = 1
    else:
        report.add("PDF006", Severity.ERROR, "PDF XMP metadata does not declare PDF/UA-1.")


def _audit_content(reader: PdfReader, report: AuditReport) -> None:
    report.metadata["link_annotations"] = sum(_link_count(page) for page in reader.pages)
    if not reader.pages:
        report.add("PDF009", Severity.ERROR, "PDF contains no pages.")
        return
    text_chars = sum(len(page.extract_text() or "") for page in reader.pages)
    report.metadata["extractable_text_characters"] = text_chars
    if not text_chars:
        report.add("PDF010", Severity.ERROR, "No extractable text was found in the PDF.")


def _link_count(page: PageObject) -> int:
    annotations = page.get("/Annots")
    if annotations is None:
        return 0
    return sum(pdf_dictionary(item).get("/Subtype") == "/Link" for item in annotations.get_object())
