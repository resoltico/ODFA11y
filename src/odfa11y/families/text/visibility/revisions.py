# SPDX-License-Identifier: AGPL-3.0-only
"""Check tracked-region identities and current-flow change marks without accepting changes."""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Annotated, Literal

lazy from lxml import etree

from odfa11y.concepts import eligible_text_node, reading_context_path
from odfa11y.concepts.review import ReviewTopic as Topic
from odfa11y.contracts import Description
from odfa11y.families.text.contexts import has_revisions
from odfa11y.odf import names as xml_names
from odfa11y.odf import qn, select_elements
from odfa11y.report import Location
from odfa11y.rules import registry as rules
lazy from odfa11y.report import Report

XML_ID = xml_names.XML_ID
KINDS = {qn("text", name) for name in ("insertion", "deletion", "format-change")}
RANGE_MARK_COUNT = 2
MARKS = {qn("text", name) for name in ("change", "change-start", "change-end")}


@dataclass(frozen=True, slots=True)
class RevisionMeasurements:
    """Measurements produced by text-revisions analysis; None denotes unmeasured data."""

    producer: Literal["text-revisions"] = field(default="text-revisions", init=False)
    revision_relationships: Annotated[
        dict[str, int] | None,
        Description("Tracked declarations, authored markers and unresolved relationships."),
    ] = None


def audit_revisions(tree: etree._ElementTree, report: Report) -> None:
    """Resolve authored marks outside history and check their point/range relationships."""
    regions = select_elements(tree, "//office:body//text:tracked-changes/text:changed-region")
    declarations: dict[str, list[etree._Element]] = defaultdict(list)
    markers: dict[str, list[etree._Element]] = defaultdict(list)
    positions = {}
    unresolved = 0
    for index, region in enumerate(regions, 1):
        identity = region.get(XML_ID) or region.get(xml_names.TEXT_ID) or ""
        declarations[identity].append(region)
        if not _valid_region(region, identity):
            report.raise_(
                rules.REVISION001,
                "Tracked-region identities are missing or contradictory.",
                location=Location.indexed(reading_context_path(region), "revision", index),
            )
            unresolved += 1
    for index, node in enumerate(select_elements(tree, "//office:body//*")):
        if _authored_mark(node):
            positions[node] = index
            markers[node.get(xml_names.TEXT_CHANGE_ID) or ""].append(node)
    if regions or positions:
        report.observe_review(Topic.HIDDEN_CONTENT)
    unresolved += _audit_missing_declarations(declarations, markers, report)
    unanchored = 0
    for identity, owners in declarations.items():
        marks = markers.get(identity, [])
        location = Location.named(reading_context_path(owners[0]), "revision", identity)
        if not marks:
            report.raise_(rules.REVISION004, location=location)
            unanchored += 1
        else:
            unresolved += _audit_region_marks(owners, marks, positions, location, report)
            if any(not eligible_text_node(mark) for mark in marks):
                report.raise_(
                    rules.REVISION005,
                    "Change anchor is inside an unestablished visibility context.",
                    location=location,
                )
                unanchored += 1
    if has_revisions(tree):
        report.raise_(
            rules.REVISION006, details={"regions": len(regions), "markers": len(positions)}
        )
    report.measure(
        RevisionMeasurements(
            revision_relationships={
                "declarations": len(regions),
                "markers": len(positions),
                "unresolved": unresolved,
                "unanchored": unanchored,
            }
        )
    )


def _audit_region_marks(
    owners: list[etree._Element],
    marks: list[etree._Element],
    positions: dict[etree._Element, int],
    location: Location,
    report: Report,
) -> int:
    if len(owners) != 1 or not _valid_marks(owners[0], marks, positions):
        report.raise_(rules.REVISION002, location=location)
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
            report.raise_(
                rules.REVISION003,
                "Change mark has no unique tracked-region declaration.",
                location=Location.named(reading_context_path(nodes[0]), "revision", identity),
            )
            unresolved += 1
    return unresolved


def _valid_region(region: etree._Element, identity: str) -> bool:
    old = region.get(xml_names.TEXT_ID)
    return (
        bool(identity)
        and (old is None or region.get(XML_ID) in {None, old})
        and len([child for child in region if child.tag in KINDS]) == 1
    )


def _authored_mark(node: etree._Element) -> bool:
    excluded = {xml_names.TEXT_TRACKED_CHANGES, xml_names.OFFICE_ANNOTATION}
    return node.tag in MARKS and not any(parent.tag in excluded for parent in node.iterancestors())


def _valid_marks(
    region: etree._Element, marks: list[etree._Element], positions: dict[etree._Element, int]
) -> bool:
    kinds = [child.tag for child in region if child.tag in KINDS]
    if len(kinds) != 1:
        return False
    if kinds[0] == xml_names.TEXT_DELETION:
        return len(marks) == 1 and marks[0].tag == xml_names.TEXT_CHANGE
    starts = [node for node in marks if node.tag == xml_names.TEXT_CHANGE_START]
    ends = [node for node in marks if node.tag == xml_names.TEXT_CHANGE_END]
    return (
        len(marks) == RANGE_MARK_COUNT
        and len(starts) == len(ends) == 1
        and positions[starts[0]] < positions[ends[0]]
        and reading_context_path(starts[0]) == reading_context_path(ends[0])
    )
