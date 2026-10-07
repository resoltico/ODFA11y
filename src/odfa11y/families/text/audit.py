# SPDX-License-Identifier: MPL-2.0
"""Audit a text document's structure: headings, graphics, tables, links, spacers, notes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.odf import Part, qn, select_elements
from odfa11y.report import rules

from .links import URI_RE, split_trailing_punctuation
from .prose import prose_slots
from .semantics import audit_headings, audit_images, audit_tables
from .spacers import spacer_candidates
from .styles import catalog_of

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report


def audit_text(document: OdfDocument, report: Report) -> None:
    """Report the accessibility findings that belong to text documents."""
    content = document.tree(Part.CONTENT)
    member = document.member_name(Part.CONTENT) or Part.CONTENT.value
    audit_headings(content, report, member)
    audit_images(content, report, member)
    audit_tables(content, report, member)
    _audit_links(content, report, member)
    _audit_empty_spacers(document, report, member)
    _audit_notes(content, report, member)
    _audit_blinking(document, report)
    _audit_style_summary(document, report)


def _audit_links(tree: etree._ElementTree, report: Report, member: str) -> None:
    """Report URLs and addresses in prose, exactly where linkification would act."""
    for index, block in enumerate(
        select_elements(tree, "//office:body//text:p | //office:body//text:h"), start=1
    ):
        for owner, attr in prose_slots(block):
            for match in URI_RE.finditer(getattr(owner, attr)):
                token, _suffix = split_trailing_punctuation(match.group(0))
                report.add(
                    rules.TXT030,
                    "Visible URL/email address is not represented by a hyperlink element.",
                    location=f"{member} paragraph {index}",
                    details={"text": token},
                )


def _audit_empty_spacers(document: OdfDocument, report: Report, member: str) -> None:
    catalog = catalog_of(document)
    styles = [
        paragraph.get(qn("text", "style-name"))
        for paragraph in spacer_candidates(document.tree(Part.CONTENT))
    ]
    if styles:
        report.add(
            rules.TXT040,
            (
                "Empty body paragraphs were found. If they are only visual "
                "spacers, prefer paragraph spacing instead."
            ),
            location=member,
            details={
                "count": len(styles),
                "with_break_semantics": sum(catalog.has_break_semantics(s) for s in styles),
                "styles": sorted({style or "(none)" for style in styles}),
            },
        )


def _audit_notes(tree: etree._ElementTree, report: Report, member: str) -> None:
    notes = select_elements(tree, "//office:body//text:note")
    if not notes:
        return
    classes: dict[str, int] = {}
    for note in notes:
        cls = note.get(qn("text", "note-class")) or "unknown"
        classes[cls] = classes.get(cls, 0) + 1
    report.add(
        rules.TXT005,
        (
            "Footnotes/endnotes are present; verify their reading order "
            "and PDF/UA export behaviour manually."
        ),
        location=member,
        details={"count": len(notes), "classes": classes},
    )


def _audit_blinking(document: OdfDocument, report: Report) -> None:
    found = [
        document.member_name(part) or part.value
        for part in (Part.CONTENT, Part.STYLES)
        if document.has(part)
        and select_elements(document.tree(part), "//*[@style:text-blinking='true']")
    ]
    if found:
        report.add(
            rules.TXT050,
            "Blinking text styling is present.",
            location=", ".join(dict.fromkeys(found)),
        )


def _audit_style_summary(document: OdfDocument, report: Report) -> None:
    report.metadata["paragraph_styles"] = style_summary(document)


def style_summary(document: OdfDocument) -> list[dict[str, object]]:
    """Summarize paragraph-style usage and effective spacing.

    Returns
    -------
    list[dict[str, object]]
        One row per paragraph style in use, most used first.

    """
    return [
        {
            "style": row.style_name,
            "count": row.count,
            "parent": row.parent,
            "spacing": row.spacing,
        }
        for row in catalog_of(document).paragraph_usage()
    ]
