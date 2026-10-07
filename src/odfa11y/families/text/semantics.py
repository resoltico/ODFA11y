# SPDX-License-Identifier: MPL-2.0
"""Audit headings, graphics and tables for accessible structure."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from odfa11y.content import (
    axis_count,
    declarations,
    graphic_keys,
    graphics_fingerprint,
    header_count,
    repeated,
    table_fingerprint,
)
from odfa11y.errors import RemediationError
from odfa11y.odf import NS, Part, qn, select_elements
from odfa11y.report import Location, rules

from .headings import MAX_HEADING_LEVEL, heading_fingerprint, heading_location
from .text import element_text

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report

MANUAL_NUMBER_RE = re.compile(r"^\s*(?P<num>\d+(?:\.\d+)*)(?P<punct>[.)])?\s+")


MIN_DATA_TABLE_DIMENSION = 2
MAX_DATA_HEADER_LENGTH = 80
MAX_SIMPLE_HEADING_NUMBER = 99


def audit_headings(tree: etree._ElementTree, report: Report) -> None:
    """Report heading-structure defects such as skipped levels and empty headings."""
    headings = select_elements(tree, "//office:body//text:h")
    report.metadata["heading_count"] = len(headings)
    previous_level: int | None = None
    for index, heading in enumerate(headings, start=1):
        raw = heading.get(qn("text", "outline-level"))
        text = element_text(heading)
        try:
            level = int(raw) if raw is not None else 0
        except ValueError:
            level = 0
        location = heading_location(heading, index)
        excerpt = {"text": text[:80], "fingerprint": heading_fingerprint(heading)}
        if not 1 <= level <= MAX_HEADING_LEVEL:
            report.add(
                rules.TXT001,
                "Heading has no valid text:outline-level.",
                location=location,
                details=excerpt,
            )
            continue
        if previous_level is None and level > 1:
            report.add(
                rules.TXT002,
                f"Heading hierarchy starts at level {level}; expected level 1.",
                location=location,
                details=excerpt,
            )
        elif previous_level is not None and level > previous_level + 1:
            report.add(
                rules.TXT002,
                f"Heading hierarchy skips from level {previous_level} to {level}.",
                location=location,
                details=excerpt,
            )
        previous_level = level
        if _looks_manually_numbered_heading(text):
            report.add(
                rules.TXT003,
                (
                    "Heading appears to use manually typed numbering; integrated "
                    "numbering is safer for accessible export."
                ),
                location=location,
                details={"text": text},
            )
    if not headings:
        report.add(
            rules.TXT004,
            "No structural headings were found. This may be legitimate for a very short document.",
            location=Location(Part.CONTENT.value),
        )


def audit_images(document: OdfDocument, report: Report) -> None:
    """Report graphics and embedded objects that lack alternative text."""
    tree = document.tree(Part.CONTENT)
    frames = select_elements(
        tree, "//office:body//draw:frame[draw:image or draw:object or draw:object-ole]"
    )
    all_frames = select_elements(tree, "//office:body//draw:frame")
    report.metadata["graphic_object_count"] = len(frames)
    for index, frame in enumerate(frames, start=1):
        title = frame.findtext("svg:title", namespaces=NS)
        desc = frame.findtext("svg:desc", namespaces=NS)
        declared_name = frame.get(qn("draw", "name"))
        image = frame.find("draw:image", NS)
        href = image.get(qn("xlink", "href")) if image is not None else None
        selector = declared_name or href
        addressed = [f for f in all_frames if selector in graphic_keys(f)] if selector else [frame]
        if not ((title and title.strip()) or (desc and desc.strip())):
            report.add(
                rules.TXT010,
                "Graphic object has neither accessible title nor description.",
                location=(
                    Location.named(Part.CONTENT, "frame", declared_name)
                    if declared_name
                    else Location.indexed(Part.CONTENT, "frame", index)
                ),
                details={
                    "frame": declared_name,
                    "href": href,
                    "fingerprint": graphics_fingerprint(document, addressed),
                },
            )


def audit_tables(tree: etree._ElementTree, report: Report) -> None:
    """Report table structure defects such as missing header rows."""
    tables = select_elements(tree, "//office:body//table:table")
    report.metadata["table_count"] = len(tables)
    for index, table in enumerate(tables, start=1):
        declared_name = table.get(qn("table", "name"))
        location = (
            Location.named(Part.CONTENT, "table", declared_name)
            if declared_name
            else Location.indexed(Part.CONTENT, "table", index)
        )
        merged = select_elements(
            table,
            (
                ".//*[@table:number-columns-spanned or "
                "@table:number-rows-spanned] | .//office:body//table:covered-table-cell"
            ),
        )
        if merged:
            report.add(
                rules.TXT020,
                (
                    "Table contains merged/split-cell structures that are "
                    "problematic for PDF/UA export."
                ),
                location=location,
                details={"merged_markers": len(merged)},
            )

        try:
            row_count = axis_count(table, "rows")
            headers = header_count(table, "rows") + header_count(table, "columns")
            rows = declarations(table, "rows")
            data_like = _looks_like_data_table(rows, row_count)
            fingerprint = table_fingerprint(table)
        except RemediationError as exc:
            report.add(rules.TXT022, str(exc), location=location)
            continue
        if not headers and data_like:
            report.add(
                rules.TXT021,
                "Table looks data-like but has no semantic header rows or columns.",
                location=location,
                details={"table": declared_name, "rows": row_count, "fingerprint": fingerprint},
            )


def _looks_like_data_table(rows: list[etree._Element], row_count: int) -> bool:
    if row_count < MIN_DATA_TABLE_DIMENSION or not rows:
        return False
    first = select_elements(rows[0], "./table:table-cell")
    cells = sum(repeated(cell, "number-columns-repeated") for cell in first)
    if cells < MIN_DATA_TABLE_DIMENSION:
        return False
    first_text = [(element_text(cell), repeated(cell, "number-columns-repeated")) for cell in first]
    if sum(count for text, count in first_text if text.strip()) < MIN_DATA_TABLE_DIMENSION:
        return False
    # Conservative: long narrative cells are more likely to belong to a layout table.
    return all(len(text) <= MAX_DATA_HEADER_LENGTH for text, _ in first_text if text.strip())


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
