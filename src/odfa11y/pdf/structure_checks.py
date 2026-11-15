# SPDX-License-Identifier: MPL-2.0
"""Check a PDF's logical structure: roles, headings, lists, tables, figures, links, content."""

from collections import Counter
from dataclasses import dataclass, field
from typing import Annotated, Literal
lazy from collections.abc import Iterable

lazy from pypdf import PageObject
lazy from pypdf.generic import DictionaryObject

from odfa11y.contracts import Description
from odfa11y.pdf.link_structure import check_link_structure
from odfa11y.pdf.marked_content import check_marked_content
from odfa11y.pdf.structure_walk import build_tree, role_map_of
from odfa11y.rules import registry as rules
lazy from odfa11y.pdf.link_structure import LinkAnnotation
lazy from odfa11y.pdf.structure_walk import StructureNode
lazy from odfa11y.report import Report

LIST_CHILDREN = {"LI", "L", "Caption"}
LIST_ITEM_CHILDREN = {"Lbl", "LBody"}
TABLE_CHILDREN = {"TR", "THead", "TBody", "TFoot", "Caption"}
ROW_GROUP_CHILDREN = {"TR"}
ROW_CHILDREN = {"TH", "TD"}
ROW_GROUPS = {"THead", "TBody", "TFoot"}
MIN_ROWS_FOR_HEADERS = 2
HEADING_ROLE_LENGTH = 2


@dataclass(frozen=True, slots=True)
class PdfStructureMeasurements:
    """Measurements produced by pdf-structure analysis; None denotes unmeasured data."""

    producer: Literal["pdf-structure"] = field(default="pdf-structure", init=False)
    structure_tags: Annotated[
        dict[str, int] | None, Description("Reachable structure roles and their counts.")
    ] = None
    role_map: Annotated[
        dict[str, str] | None, Description("PDF custom-to-standard structure role mapping.")
    ] = None


@dataclass(frozen=True, slots=True)
class StructureAnalysis:
    described_graphics: int
    tags: dict[str, int]
    link_annotations: int


def audit_structure(
    root: DictionaryObject,
    report: Report,
    annotations: list[LinkAnnotation],
    pages: Iterable[PageObject],
) -> StructureAnalysis:
    """Record structure tags and report structure, link and marked-content defects.

    Content is inspected even when the structure tree is absent.

    Returns
    -------
    int
        Described Figures reconciled with graphical content on actual pages.

    """
    top = build_tree(root)
    nodes = [node for node in top.walk() if node is not top]
    counts = Counter(node.tag for node in nodes)
    report.measure(PdfStructureMeasurements(structure_tags=dict(sorted(counts.items()))))
    role_map = role_map_of(root)
    if role_map:
        report.measure(PdfStructureMeasurements(role_map=dict(sorted(role_map.items()))))
    check_link_structure(annotations, nodes, report)
    graphic_count = check_marked_content(pages, nodes, report)
    _check_roles(nodes, report)
    _check_figures(nodes, report)
    _check_headings(nodes, report)
    _check_lists(nodes, report)
    _check_tables(nodes, report)
    return StructureAnalysis(graphic_count, dict(counts), len(annotations))


def _check_roles(nodes: list[StructureNode], report: Report) -> None:
    unmapped = sorted({node.tag for node in nodes if node.role is None})
    if unmapped:
        report.raise_(
            rules.PDF011,
            "Custom structure types do not resolve to standard types through /RoleMap.",
            details={"unmapped_structure_types": unmapped},
        )
    if not any(_heading_level(node) for node in nodes):
        report.raise_(rules.PDF008, "No PDF heading structure tags were detected.")


def _check_figures(nodes: list[StructureNode], report: Report) -> None:
    figures = [node for node in nodes if node.role == "Figure"]
    missing = [node for node in figures if not _has_text(node.element.get("/Alt"))]
    if missing:
        report.raise_(
            rules.PDF007,
            "One or more Figure structure elements have no /Alt text.",
            details={
                "figure_xrefs": [_xref(node) for node in figures],
                "missing_alt_xrefs": [_xref(node) for node in missing],
            },
        )


def _check_headings(nodes: list[StructureNode], report: Report) -> None:
    previous = 0
    skips: list[str] = []
    for node in nodes:
        level = _heading_level(node)
        if not level:
            continue
        if level > previous + 1:
            skips.append(f"H{previous} to H{level}" if previous else f"start to H{level}")
        previous = level
    if skips:
        report.raise_(rules.PDF012, details={"skips": skips})


def _check_lists(nodes: list[StructureNode], report: Report) -> None:
    problems = []
    for node in nodes:
        if node.role == "L":
            problems += [
                f"L contains {child.role}"
                for child in node.children
                if child.role not in LIST_CHILDREN
            ]
        elif node.role == "LI":
            problems += [
                f"LI contains {child.role}"
                for child in node.children
                if child.role not in LIST_ITEM_CHILDREN
            ]
    if problems:
        report.raise_(rules.PDF013, details={"problems": sorted(set(problems))})


def _check_tables(nodes: list[StructureNode], report: Report) -> None:
    problems = []
    for node in nodes:
        allowed = {
            "Table": TABLE_CHILDREN,
            "TR": ROW_CHILDREN,
            **dict.fromkeys(ROW_GROUPS, ROW_GROUP_CHILDREN),
        }.get(node.role or "")
        if allowed is not None:
            problems += [
                f"{node.role} contains {child.role}"
                for child in node.children
                if child.role not in allowed
            ]
        if node.role == "Table":
            descendants = [n for n in node.walk() if n is not node]
            rows = sum(n.role == "TR" for n in descendants)
            if rows >= MIN_ROWS_FOR_HEADERS and not any(n.role == "TH" for n in descendants):
                report.raise_(rules.PDF015, details={"rows": rows})
    if problems:
        report.raise_(rules.PDF014, details={"problems": sorted(set(problems))})


def _heading_level(node: StructureNode) -> int:
    role = node.role or ""
    return (
        int(role[1])
        if role[:1] == "H" and role[1:].isdigit() and len(role) == HEADING_ROLE_LENGTH
        else 0
    )


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _xref(node: StructureNode) -> int:
    reference = node.element.indirect_reference
    return reference.idnum if reference is not None else 0
