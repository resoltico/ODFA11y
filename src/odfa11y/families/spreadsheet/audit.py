# SPDX-License-Identifier: MPL-2.0
"""Audit a spreadsheet: sheet names, header rows, merged cells, graphics, links and clutter."""

import re
from collections import Counter

lazy from lxml import etree

from odfa11y.concepts import (
    SHAPE_TAGS,
    GraphicIdentity,
    audit_graphic_role,
    document_links,
    eligible_text_node,
    link_decision,
    link_has_description,
    link_location,
    visible_words,
)
from odfa11y.concepts.kinds import GRAPHIC_ALTERNATIVE, LINK_DESCRIPTION
from odfa11y.decisions import OpenDecision
from odfa11y.families.spreadsheet.kinds import SHEET_NAME
from odfa11y.families.spreadsheet.sheets import (
    cell_text,
    is_data_sheet,
    is_empty,
    sheet_name,
    sheets,
)
from odfa11y.families.spreadsheet.snapshot import sheet_fingerprint
from odfa11y.odf import NS, Part, select_elements
from odfa11y.odf import names as xml_names
from odfa11y.report import FactKeys, Location
from odfa11y.rules import registry as rules
from odfa11y.targets import Fingerprint, Target
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.report import Report

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
    all_sheets = sheets(content)
    report.facts[FactKeys.SHEET_COUNT] = len(all_sheets)
    _audit_names(document, all_sheets, report)
    _audit_data_sheets(all_sheets, report)
    _audit_graphics(document, report)
    _audit_links(all_sheets, report)
    for index, link in enumerate(document_links(document), 1):
        if not link_has_description(link):
            report.raise_(
                rules.LINK003,
                location=link_location(link, index),
                decision=link_decision(document, link, index, LINK_DESCRIPTION, rules.LINK003.id),
            )
    _audit_trailing_empty_sheets(all_sheets, report)
    _audit_hidden(content, all_sheets, report)


def _location(index: int, sheet: etree._Element) -> Location:
    name = sheet_name(sheet)
    return (
        Location.named(Part.CONTENT, "sheet", name)
        if name
        else Location.indexed(Part.CONTENT, "sheet", index)
    )


def _audit_names(document: OdfDocument, all_sheets: list[etree._Element], report: Report) -> None:
    names = Counter(sheet_name(sheet) for sheet in all_sheets)
    for index, sheet in enumerate(all_sheets, start=1):
        name = sheet_name(sheet)
        rule = (
            rules.SHEET001
            if not name.strip()
            else (rules.SHEET002 if DEFAULT_SHEET_NAME.fullmatch(name.strip()) else None)
        )
        if rule is None:
            continue
        decision = (
            OpenDecision(
                SHEET_NAME,
                Target(
                    Location.indexed(Part.CONTENT, "sheet", index).path,
                    Fingerprint(sheet_fingerprint(document, sheet)),
                ),
                {"name": name},
            )
            if names[name] == 1
            else None
        )
        report.raise_(
            rule,
            location=Location.indexed(Part.CONTENT, "sheet", index),
            details={"sheet": name},
            decision=decision,
        )


def _audit_data_sheets(all_sheets: list[etree._Element], report: Report) -> None:
    for index, sheet in enumerate(all_sheets, start=1):
        if not is_data_sheet(sheet):
            continue
        if not select_elements(sheet, ".//table:table-header-rows"):
            report.raise_(
                rules.TABLE004,
                "Sheet looks like a table of data but marks no header rows to repeat.",
                location=_location(index, sheet),
                details={"sheet": sheet_name(sheet)},
            )
        merged = select_elements(sheet, MERGED_CELLS)
        if merged:
            report.raise_(
                rules.TABLE005,
                "Data sheet merges cells, which breaks row and column navigation.",
                location=_location(index, sheet),
                details={"sheet": sheet_name(sheet), "merged_cells": len(merged)},
            )


def _audit_graphics(document: OdfDocument, report: Report) -> None:
    content = document.tree(Part.CONTENT)
    frames = [
        node
        for node in select_elements(content, "//office:body//*")
        if node.tag in SHAPE_TAGS and node.tag != xml_names.DRAW_G and eligible_text_node(node)
    ]
    report.facts[FactKeys.SHEET_GRAPHIC_COUNT] = len(frames)
    for group in select_elements(document.tree(Part.CONTENT), "//office:body//draw:g"):
        audit_graphic_role(document, group, report)
    identity = GraphicIdentity(document, frames)
    for frame in frames:
        if audit_graphic_role(document, frame, report):
            continue
        if visible_words(frame) and not select_elements(
            frame, "./draw:image | ./draw:object | ./draw:object-ole"
        ):
            continue
        title = frame.findtext("svg:title", namespaces=NS)
        desc = frame.findtext("svg:desc", namespaces=NS)
        if (title and title.strip()) or (desc and desc.strip()):
            continue
        declared_name = frame.get(xml_names.DRAW_NAME)
        image = frame.find("draw:image", NS)
        href = image.get(xml_names.XLINK_HREF) if image is not None else None
        report.raise_(
            rules.GRAPHIC003,
            "Picture, chart or object has neither accessible title nor description.",
            location=Location(identity.target(frame)),
            details={
                "frame": declared_name,
                "href": href,
            },
            decision=identity.open_decision(frame, GRAPHIC_ALTERNATIVE, rules.GRAPHIC003.id),
        )


def _audit_links(all_sheets: list[etree._Element], report: Report) -> None:
    for index, sheet in enumerate(all_sheets, start=1):
        for link in select_elements(sheet, ".//text:a"):
            text = cell_text(link)
            if RAW_URL.fullmatch(text) and not link.get(xml_names.OFFICE_TITLE, "").strip():
                report.raise_(
                    rules.LINK002,
                    "Hyperlink text is a raw address instead of a description of its target.",
                    location=_location(index, sheet),
                    details={"text": text},
                )


def _audit_trailing_empty_sheets(all_sheets: list[etree._Element], report: Report) -> None:
    empty = [is_empty(sheet) for sheet in all_sheets]
    kept = max((index for index, blank in enumerate(empty) if not blank), default=0)
    for index, sheet in enumerate(all_sheets):
        if index > kept and empty[index]:
            report.raise_(
                rules.SHEET007,
                "Sheet is empty and follows the last sheet with content.",
                location=_location(index + 1, sheet),
                details={"sheet": sheet_name(sheet)},
            )


def _audit_hidden(
    content: etree._ElementTree, all_sheets: list[etree._Element], report: Report
) -> None:
    hidden_styles = {
        style.get(xml_names.STYLE_NAME) for style in select_elements(content, HIDDEN_SHEET_STYLES)
    } - {None}
    sheet_names = [
        sheet_name(sheet)
        for sheet in all_sheets
        if sheet.get(xml_names.TABLE_STYLE_NAME) in hidden_styles
    ]
    rows = len(select_elements(content, HIDDEN_ROWS))
    columns = len(select_elements(content, HIDDEN_COLUMNS))
    if sheet_names or rows or columns:
        report.raise_(
            rules.HIDDEN001,
            "Hidden sheets, rows or columns hold content that not every reader is told about.",
            location=Location(Part.CONTENT.value),
            details={"sheets": sheet_names, "rows": rows, "columns": columns},
        )
