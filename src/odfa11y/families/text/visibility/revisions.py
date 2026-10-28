# SPDX-License-Identifier: MPL-2.0
"""Check tracked-region identities and current-flow change marks without accepting changes."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from odfa11y.content import eligible_text_node, reading_context_path
from odfa11y.families.text.contexts import has_revisions
from odfa11y.odf import qn, select_elements
from odfa11y.report import FactKeys, Location, rules

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.report import Report

XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
KINDS = {qn("text", name) for name in ("insertion", "deletion", "format-change")}
RANGE_MARK_COUNT = 2
MARKS = {qn("text", name) for name in ("change", "change-start", "change-end")}


def audit_revisions(tree: etree._ElementTree, report: Report) -> None:
    """Resolve authored marks outside history and check their point/range relationships."""
    regions = select_elements(tree, "//office:body//text:tracked-changes/text:changed-region")
    declarations: dict[str, list[etree._Element]] = defaultdict(list)
    markers: dict[str, list[etree._Element]] = defaultdict(list)
    positions = {}
    unresolved = 0
    for index, region in enumerate(regions, 1):
        identity = region.get(XML_ID) or region.get(qn("text", "id")) or ""
        declarations[identity].append(region)
        if not _valid_region(region, identity):
            report.add(
                rules.REVISION002,
                "Tracked-region identities are missing or contradictory.",
                location=Location.indexed(reading_context_path(region), "revision", index),
            )
            unresolved += 1
    for index, node in enumerate(select_elements(tree, "//office:body//*")):
        if _authored_mark(node):
            positions[node] = index
            markers[node.get(qn("text", "change-id")) or ""].append(node)
    unresolved += _audit_missing_declarations(declarations, markers, report)
    unanchored = 0
    for identity, owners in declarations.items():
        marks = markers.get(identity, [])
        location = Location.named(reading_context_path(owners[0]), "revision", identity)
        if not marks:
            report.add(rules.REVISION003, location=location)
            unanchored += 1
        else:
            unresolved += _audit_region_marks(owners, marks, positions, location, report)
            if any(not eligible_text_node(mark) for mark in marks):
                report.add(
                    rules.REVISION003,
                    "Change anchor is inside an unestablished visibility context.",
                    location=location,
                )
                unanchored += 1
    if has_revisions(tree):
        report.add(rules.REVISION001, details={"regions": len(regions), "markers": len(positions)})
    report.facts[FactKeys.TEXT_REVISION_RELATIONSHIPS] = {
        "declarations": len(regions),
        "markers": len(positions),
        "unresolved": unresolved,
        "unanchored": unanchored,
    }


def _audit_region_marks(
    owners: list[etree._Element],
    marks: list[etree._Element],
    positions: dict[etree._Element, int],
    location: Location,
    report: Report,
) -> int:
    if len(owners) != 1 or not _valid_marks(owners[0], marks, positions):
        report.add(rules.REVISION002, location=location)
        return 1
    return 0


def _audit_missing_declarations(
    declarations: dict[str, list[etree._Element]],
    markers: dict[str, list[etree._Element]],
    report: Report,
) -> int:
    unresolved = 0
    for identity, nodes in markers.items():
        if len(declarations.get(identity, [])) != 1:
            report.add(
                rules.REVISION002,
                "Change mark has no unique tracked-region declaration.",
                location=Location.named(reading_context_path(nodes[0]), "revision", identity),
            )
            unresolved += 1
    return unresolved


def _valid_region(region: etree._Element, identity: str) -> bool:
    old = region.get(qn("text", "id"))
    return (
        bool(identity)
        and (old is None or region.get(XML_ID) in {None, old})
        and len([child for child in region if child.tag in KINDS]) == 1
    )


def _authored_mark(node: etree._Element) -> bool:
    excluded = {qn("text", "tracked-changes"), qn("office", "annotation")}
    return node.tag in MARKS and not any(parent.tag in excluded for parent in node.iterancestors())


def _valid_marks(
    region: etree._Element, marks: list[etree._Element], positions: dict[etree._Element, int]
) -> bool:
    kinds = [child.tag for child in region if child.tag in KINDS]
    if len(kinds) != 1:
        return False
    if kinds[0] == qn("text", "deletion"):
        return len(marks) == 1 and marks[0].tag == qn("text", "change")
    starts = [node for node in marks if node.tag == qn("text", "change-start")]
    ends = [node for node in marks if node.tag == qn("text", "change-end")]
    return (
        len(marks) == RANGE_MARK_COUNT
        and len(starts) == len(ends) == 1
        and positions[starts[0]] < positions[ends[0]]
        and reading_context_path(starts[0]) == reading_context_path(ends[0])
    )
