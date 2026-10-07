# SPDX-License-Identifier: MPL-2.0
"""Audit a spreadsheet: sheet names, header rows, merged cells, graphics, links and clutter."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from odfa11y.odf import NS, Part, qn, select_elements
from odfa11y.report import rules

from .objects import frame_keys, frames_fingerprint
from .sheets import cell_text, is_data_sheet, is_empty, sheet_name, sheets

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report

DEFAULT_SHEET_NAME = re.compile(r"sheet\s*\d+", re.IGNORECASE)
RAW_URL = re.compile(r"(?:[a-z][a-z0-9+.-]*://|www\.|mailto:)\S+", re.IGNORECASE)
MERGED_CELLS = (
    ".//table:table-cell[@table:number-columns-spanned > 1 or @table:number-rows-spanned > 1]"
)
HIDDEN_SHEET_STYLES = (
    "//office:automatic-styles/style:style[@style:family='table']"
    "[style:table-properties/@table:display='false']"
)
HIDDEN_ROWS = ".//table:table-row[@table:visibility='collapse' or @table:visibility='filter']"
HIDDEN_COLUMNS = ".//table:table-column[@table:visibility='collapse' or @table:visibility='filter']"


def audit_spreadsheet(document: OdfDocument, report: Report) -> None:
    """Report the accessibility findings that belong to spreadsheets."""
    content = document.tree(Part.CONTENT)
    member = document.member_name(Part.CONTENT) or Part.CONTENT.value
    all_sheets = sheets(content)
    report.metadata["sheet_count"] = len(all_sheets)
    _audit_names(all_sheets, report, member)
    _audit_data_sheets(all_sheets, report, member)
    _audit_graphics(content, report, member)
    _audit_links(all_sheets, report, member)
    _audit_trailing_empty_sheets(all_sheets, report, member)
    _audit_hidden(content, all_sheets, report, member)


def _location(member: str, index: int, sheet: etree._Element) -> str:
    return f"{member} sheet {index}: {sheet_name(sheet)}"


def _audit_names(all_sheets: list[etree._Element], report: Report, member: str) -> None:
    for index, sheet in enumerate(all_sheets, start=1):
        name = sheet_name(sheet)
        if not name.strip():
            report.add(
                rules.SHEET001,
                "Sheet has no name, so a reader cannot tell it from the others.",
                location=f"{member} sheet {index}",
            )
        elif DEFAULT_SHEET_NAME.fullmatch(name.strip()):
            report.add(
                rules.SHEET002,
                "Sheet keeps its default name, which says nothing about its content.",
                location=_location(member, index, sheet),
                details={"sheet": name},
            )


def _audit_data_sheets(all_sheets: list[etree._Element], report: Report, member: str) -> None:
    for index, sheet in enumerate(all_sheets, start=1):
        if not is_data_sheet(sheet):
            continue
        if not select_elements(sheet, ".//table:table-header-rows"):
            report.add(
                rules.SHEET003,
                "Sheet looks like a table of data but marks no header rows to repeat.",
                location=_location(member, index, sheet),
                details={"sheet": sheet_name(sheet)},
            )
        merged = select_elements(sheet, MERGED_CELLS)
        if merged:
            report.add(
                rules.SHEET004,
                "Data sheet merges cells, which breaks row and column navigation.",
                location=_location(member, index, sheet),
                details={"sheet": sheet_name(sheet), "merged_cells": len(merged)},
            )


def _audit_graphics(content: etree._ElementTree, report: Report, member: str) -> None:
    frames = select_elements(
        content, "//office:body//draw:frame[draw:image or draw:object or draw:object-ole]"
    )
    report.metadata["graphic_object_count"] = len(frames)
    everything = select_elements(content, "//office:body//draw:frame")
    for index, frame in enumerate(frames, start=1):
        title = frame.findtext("svg:title", namespaces=NS)
        desc = frame.findtext("svg:desc", namespaces=NS)
        if (title and title.strip()) or (desc and desc.strip()):
            continue
        declared_name = frame.get(qn("draw", "name"))
        image = frame.find("draw:image", NS)
        href = image.get(qn("xlink", "href")) if image is not None else None
        selector = declared_name or href
        addressed = [f for f in everything if selector in frame_keys(f)] if selector else [frame]
        report.add(
            rules.SHEET005,
            "Picture, chart or object has neither accessible title nor description.",
            location=f"{member} draw:frame {declared_name or f'frame-{index}'}",
            details={
                "frame": declared_name,
                "href": href,
                "fingerprint": frames_fingerprint(addressed),
            },
        )


def _audit_links(all_sheets: list[etree._Element], report: Report, member: str) -> None:
    for index, sheet in enumerate(all_sheets, start=1):
        for link in select_elements(sheet, ".//text:a"):
            text = cell_text(link)
            if RAW_URL.fullmatch(text):
                report.add(
                    rules.SHEET006,
                    "Hyperlink text is a raw address instead of a description of its target.",
                    location=_location(member, index, sheet),
                    details={"text": text},
                )


def _audit_trailing_empty_sheets(
    all_sheets: list[etree._Element], report: Report, member: str
) -> None:
    empty = [is_empty(sheet) for sheet in all_sheets]
    kept = max((index for index, blank in enumerate(empty) if not blank), default=0)
    for index, sheet in enumerate(all_sheets):
        if index > kept and empty[index]:
            report.add(
                rules.SHEET007,
                "Sheet is empty and follows the last sheet with content.",
                location=_location(member, index + 1, sheet),
                details={"sheet": sheet_name(sheet)},
            )


def _audit_hidden(
    content: etree._ElementTree, all_sheets: list[etree._Element], report: Report, member: str
) -> None:
    hidden_styles = {
        style.get(qn("style", "name")) for style in select_elements(content, HIDDEN_SHEET_STYLES)
    } - {None}
    sheet_names = [
        sheet_name(sheet)
        for sheet in all_sheets
        if sheet.get(qn("table", "style-name")) in hidden_styles
    ]
    rows = len(select_elements(content, HIDDEN_ROWS))
    columns = len(select_elements(content, HIDDEN_COLUMNS))
    if sheet_names or rows or columns:
        report.add(
            rules.SHEET008,
            "Hidden sheets, rows or columns hold content that not every reader is told about.",
            location=member,
            details={"sheets": sheet_names, "rows": rows, "columns": columns},
        )
