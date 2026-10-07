# SPDX-License-Identifier: MPL-2.0
"""Audit headings, graphics and tables for accessible structure."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from odfa11y.odf import NS, element_text, qn, select_elements
from odfa11y.report import Severity

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.report import AuditReport

MANUAL_NUMBER_RE = re.compile(r"^\s*(?P<num>\d+(?:\.\d+)*)(?P<punct>[.)])?\s+")


MIN_DATA_TABLE_DIMENSION = 2
MAX_DATA_HEADER_LENGTH = 80
MAX_SIMPLE_HEADING_NUMBER = 99


def audit_headings(tree: etree._ElementTree, report: AuditReport) -> None:
    """Report heading-structure defects such as skipped levels and empty headings."""
    headings = select_elements(tree, "//text:h")
    report.metadata["heading_count"] = len(headings)
    previous_level: int | None = None
    for index, heading in enumerate(headings, start=1):
        raw = heading.get(qn("text", "outline-level"))
        text = element_text(heading)
        try:
            level = int(raw) if raw is not None else 0
        except ValueError:
            level = 0
        location = f"content.xml heading {index}: {text[:80]}"
        if level < 1:
            report.add(
                "SEM001",
                Severity.ERROR,
                "Heading has no valid text:outline-level.",
                location=location,
            )
            continue
        if previous_level is None and level > 1:
            report.add(
                "SEM002",
                Severity.ERROR,
                f"Heading hierarchy starts at level {level}; expected level 1.",
                location=location,
            )
        elif previous_level is not None and level > previous_level + 1:
            report.add(
                "SEM002",
                Severity.ERROR,
                f"Heading hierarchy skips from level {previous_level} to {level}.",
                location=location,
            )
        previous_level = level
        if _looks_manually_numbered_heading(text):
            report.add(
                "SEM003",
                Severity.WARNING,
                (
                    "Heading appears to use manually typed numbering; integrated "
                    "numbering is safer for accessible export."
                ),
                location=location,
                details={"text": text},
                fixable=False,
            )
    if not headings:
        report.add(
            "SEM004",
            Severity.INFO,
            "No structural headings were found. This may be legitimate for a very short document.",
            location="content.xml",
        )


def audit_images(tree: etree._ElementTree, report: AuditReport) -> None:
    """Report graphics and embedded objects that lack alternative text."""
    frames = select_elements(tree, "//draw:frame[draw:image or draw:object or draw:object-ole]")
    report.metadata["graphic_object_count"] = len(frames)
    for index, frame in enumerate(frames, start=1):
        title = frame.findtext("svg:title", namespaces=NS)
        desc = frame.findtext("svg:desc", namespaces=NS)
        name = frame.get(qn("draw", "name")) or f"frame-{index}"
        image = frame.find("draw:image", NS)
        href = image.get(qn("xlink", "href")) if image is not None else None
        if not ((title and title.strip()) or (desc and desc.strip())):
            report.add(
                "IMG001",
                Severity.ERROR,
                "Graphic object has neither accessible title nor description.",
                location=f"content.xml draw:frame {name}",
                details={"href": href},
                fixable=True,
            )


def audit_tables(tree: etree._ElementTree, report: AuditReport) -> None:
    """Report table structure defects such as missing header rows."""
    tables = select_elements(tree, "//table:table")
    report.metadata["table_count"] = len(tables)
    for index, table in enumerate(tables, start=1):
        name = table.get(qn("table", "name")) or f"table-{index}"
        location = f"content.xml table {name}"
        merged = select_elements(
            table,
            (
                ".//*[@table:number-columns-spanned or "
                "@table:number-rows-spanned] | .//table:covered-table-cell"
            ),
        )
        if merged:
            report.add(
                "TBL001",
                Severity.ERROR,
                (
                    "Table contains merged/split-cell structures that are "
                    "problematic for PDF/UA export."
                ),
                location=location,
                details={"merged_markers": len(merged)},
                fixable=False,
            )

        direct_rows = select_elements(table, "./table:table-row")
        header_rows = select_elements(table, "./table:table-header-rows/table:table-row")
        if not header_rows and _looks_like_data_table(direct_rows):
            report.add(
                "TBL002",
                Severity.WARNING,
                "Table looks data-like but has no semantic table:table-header-rows.",
                location=location,
                details={"rows": len(direct_rows)},
                fixable=True,
            )


def _looks_like_data_table(rows: list[etree._Element]) -> bool:
    if len(rows) < MIN_DATA_TABLE_DIMENSION:
        return False
    first = select_elements(rows[0], "./table:table-cell")
    second = select_elements(rows[1], "./table:table-cell")
    if len(first) < MIN_DATA_TABLE_DIMENSION or len(second) < MIN_DATA_TABLE_DIMENSION:
        return False
    first_text = [element_text(cell) for cell in first]
    if sum(bool(t.strip()) for t in first_text) < MIN_DATA_TABLE_DIMENSION:
        return False
    # Deliberately conservative: long narrative cells are more likely to be layout tables.
    return all(len(t) <= MAX_DATA_HEADER_LENGTH for t in first_text if t.strip())


def _looks_manually_numbered_heading(text: str) -> bool:
    match = MANUAL_NUMBER_RE.match(text)
    if not match:
        return False
    number = match.group("num")
    punct = match.group("punct")
    if "." in number or punct:
        return True
    try:
        return int(number) <= MAX_SIMPLE_HEADING_NUMBER
    except ValueError:
        return False
