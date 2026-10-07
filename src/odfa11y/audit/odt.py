# SPDX-License-Identifier: MPL-2.0
"""Run the read-only audit of an ODT document and collect its findings."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.errors import PackageError
from odfa11y.odf import (
    REQUIRED_XML,
    URI_RE,
    OdtDocument,
    element_text,
    is_empty_paragraph,
    qn,
    select_elements,
    split_trailing_punctuation,
)
from odfa11y.report import Report, rules

from .metadata import audit_metadata
from .package import audit_package, audit_schema, audit_versions
from .semantics import audit_headings, audit_images, audit_tables

if TYPE_CHECKING:
    from lxml import etree


def audit_odt(source: str | Path, *, schema: bool = False) -> Report:
    """Audit package structure and document semantics without modifying the source.

    Returns
    -------
    Report
        Package and document findings, plus discovered metadata. With ``schema``, members
        are also validated against the bundled ODF schema for the declared version.

    """
    source = Path(source)
    report = Report(kind="odt", subject=str(source))
    try:
        document = OdtDocument.open(source)
    except (PackageError, OSError) as exc:
        report.add(rules.PKG000, str(exc), location=str(source))
        return report

    audit_package(document.package, report)
    if any(not document.has(name) for name in REQUIRED_XML):
        return report
    members = [*REQUIRED_XML, *(["settings.xml"] if document.has("settings.xml") else [])]
    unparsable = False
    for name in members:
        try:
            document.tree(name)
        except PackageError as exc:
            report.add(rules.XML001, str(exc), location=name)
            unparsable = unparsable or name in REQUIRED_XML
    if unparsable:
        return report

    content = document.tree("content.xml")
    audit_versions(document, report)
    audit_metadata(document.tree("meta.xml"), document.tree("styles.xml"), report)
    audit_headings(content, report)
    audit_images(content, report)
    audit_tables(content, report)
    _audit_links(content, report)
    _audit_empty_spacers(document, report)
    _audit_notes(content, report)
    _audit_blinking(document, report)
    _audit_style_summary(document, report)
    if schema:
        audit_schema(document, report)
    return report


def _audit_links(tree: etree._ElementTree, report: Report) -> None:
    blocks = select_elements(tree, "//text:p | //text:h")
    for index, block in enumerate(blocks, start=1):
        text = element_text(block)
        matches = list(URI_RE.finditer(text))
        if not matches:
            continue
        linked_texts = [element_text(a) for a in select_elements(block, ".//text:a")]
        for match in matches:
            token, _suffix = split_trailing_punctuation(match.group(0))
            if not any(token in linked for linked in linked_texts):
                report.add(
                    rules.LNK001,
                    "Visible URL/email address is not represented by a hyperlink element.",
                    location=f"content.xml paragraph {index}",
                    details={"text": token},
                )


def _audit_empty_spacers(document: OdtDocument, report: Report) -> None:
    catalog = document.catalog
    empty = []
    for p in select_elements(document.tree("content.xml"), "//text:p"):
        if not is_empty_paragraph(p):
            continue
        if select_elements(
            p, "ancestor::table:table-cell | ancestor::draw:text-box | ancestor::office:annotation"
        ):
            continue
        style_name = p.get(qn("text", "style-name"))
        empty.append((style_name, catalog.has_break_semantics(style_name)))
    if empty:
        report.add(
            rules.LAY001,
            (
                "Empty body paragraphs were found. If they are only visual "
                "spacers, prefer paragraph spacing instead."
            ),
            location="content.xml",
            details={
                "count": len(empty),
                "with_break_semantics": sum(item[1] for item in empty),
                "styles": sorted({item[0] or "(none)" for item in empty}),
            },
        )


def _audit_notes(tree: etree._ElementTree, report: Report) -> None:
    notes = select_elements(tree, "//text:note")
    if not notes:
        return
    classes: dict[str, int] = {}
    for note in notes:
        cls = note.get(qn("text", "note-class")) or "unknown"
        classes[cls] = classes.get(cls, 0) + 1
    report.add(
        rules.SEM005,
        (
            "Footnotes/endnotes are present; verify their reading order "
            "and PDF/UA export behaviour manually."
        ),
        location="content.xml",
        details={"count": len(notes), "classes": classes},
    )


def _audit_blinking(document: OdtDocument, report: Report) -> None:
    found = [
        name
        for name in ("content.xml", "styles.xml")
        if select_elements(document.tree(name), "//*[@style:text-blinking='true']")
    ]
    if found:
        report.add(rules.STYLE001, "Blinking text styling is present.", location=", ".join(found))


def _audit_style_summary(document: OdtDocument, report: Report) -> None:
    report.metadata["paragraph_styles"] = [
        {
            "style": row.style_name,
            "count": row.count,
            "parent": row.parent,
            "spacing": row.spacing,
        }
        for row in document.catalog.paragraph_usage()
    ]
