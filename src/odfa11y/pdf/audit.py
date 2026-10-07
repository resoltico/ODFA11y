# SPDX-License-Identifier: MPL-2.0
"""Inspect parsed PDF objects for accessibility diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from lxml import etree
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from pypdf.generic import BooleanObject, StreamObject

from odfa11y.errors import ToolFailedError
from odfa11y.pdf_limits import check_limits
from odfa11y.report import Report, rules
from odfa11y.safe_xml import parse_secure

from .link_structure import link_annotations
from .structure_checks import audit_structure
from .structure_walk import pdf_dictionary

if TYPE_CHECKING:
    from pypdf.generic import DictionaryObject

PDFUA_PART = "{http://www.aiim.org/pdfua/ns/id/}part"


def audit_pdfua(pdf_path: str | Path) -> Report:
    """Inspect PDF accessibility markers without claiming full conformance.

    Returns
    -------
    Report
        Structural accessibility findings and PDF metadata.

    """
    pdf_path = Path(pdf_path)
    report = Report(kind="pdf", subject=str(pdf_path))
    try:
        _inspect(pdf_path, report)
    except (OSError, PyPdfError, ValueError, KeyError, ToolFailedError) as exc:
        report.add(rules.PDF000, f"Cannot inspect PDF: {exc}", location=pdf_path.name)
    return report


def _inspect(pdf_path: Path, report: Report) -> None:
    with pdf_path.open("rb") as stream:
        reader = PdfReader(stream, strict=True)
        check_limits(pdf_path, len(reader.pages))
        structure = _audit_metadata(reader, report)
        audit_structure(structure, report, link_annotations(reader), reader.pages)
        _audit_content(reader, report)


def _audit_metadata(reader: PdfReader, report: Report) -> DictionaryObject:
    report.metadata["pages"] = len(reader.pages)
    report.metadata["pdf_format"] = reader.pdf_header.removeprefix("%")
    title = (reader.metadata.title or "").strip() if reader.metadata else ""
    if title:
        report.metadata["title"] = title
    else:
        report.add(rules.PDF001, "PDF document title metadata is missing.")
    catalog = reader.root_object
    language = catalog.get("/Lang")
    if isinstance(language, str) and language.strip():
        report.metadata["language"] = language
    else:
        report.add(rules.PDF002, "PDF catalog /Lang is missing.")
    marked = pdf_dictionary(catalog.get("/MarkInfo")).get("/Marked")
    if not isinstance(marked, BooleanObject) or not marked.value:
        report.add(rules.PDF003, "PDF is not marked as a tagged document.")
    structure = pdf_dictionary(catalog.get("/StructTreeRoot"))
    if not structure:
        report.add(rules.PDF004, "PDF has no /StructTreeRoot.")
    display_title = pdf_dictionary(catalog.get("/ViewerPreferences")).get("/DisplayDocTitle")
    if not isinstance(display_title, BooleanObject) or not display_title.value:
        report.add(rules.PDF005, "PDF viewer preferences do not display the title.")
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
        report.metadata["pdfua_part"] = 1
    else:
        report.add(rules.PDF006, "PDF XMP metadata does not declare PDF/UA-1.")


def _audit_content(reader: PdfReader, report: Report) -> None:
    if not reader.pages:
        report.add(rules.PDF009, "PDF contains no pages.")
        return
    text_chars = sum(len(page.extract_text() or "") for page in reader.pages)
    report.metadata["extractable_text_characters"] = text_chars
    if not text_chars:
        report.add(rules.PDF010, "No extractable text was found in the PDF.")
