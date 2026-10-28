# SPDX-License-Identifier: MPL-2.0
"""Resolve Writer anchors and references without inventing missing destinations."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import unquote

from odfa11y.content import reading_context_path, visible_words
from odfa11y.families.text.contexts import text_nodes
from odfa11y.odf import Part, qn
from odfa11y.report import FactKeys, Location, rules

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report

XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
FIELDS = {
    qn("text", name + "-ref"): kind
    for name, kind in (("bookmark", "bookmark"), ("reference", "reference-mark"), ("note", "note"))
}
LINKS = {qn("text", "a"), qn("draw", "a")}
NAMED_TARGETS = {
    **{tag: qn("office", "name") for tag in LINKS},
    qn("text", "section"): qn("text", "name"),
    qn("table", "table"): qn("table", "name"),
    qn("draw", "frame"): qn("draw", "name"),
}


@dataclass
class _Index:
    nodes: list[etree._Element]
    targets: dict[tuple[str, str], set[etree._Element]] = field(
        default_factory=lambda: defaultdict(set)
    )
    ends: dict[tuple[str, str], list[etree._Element]] = field(
        default_factory=lambda: defaultdict(list)
    )
    excluded: set[tuple[str, str]] = field(default_factory=set)
    positions: dict[etree._Element, int] = field(default_factory=dict)
    locations: dict[etree._Element, Location] = field(default_factory=dict)


def audit_references(document: OdfDocument, report: Report) -> None:
    """Check destination identity, ranges and note anchor/body relationships."""
    tree = document.tree(Part.CONTENT)
    tags = {str(node.tag) for node in tree.iter() if isinstance(node.tag, str)}
    index = _Index(text_nodes(tree, *tags))
    counters: Counter[str] = Counter()
    for position, node in enumerate(index.nodes):
        context = reading_context_path(node)
        counters[context] += 1
        index.positions[node] = position
        index.locations[node] = Location.indexed(context, "reference", counters[context])
        _collect(node, index)
        if node.tag == qn("text", "note"):
            _note(node, index.locations[node], report)
    outside = _Index([])
    current = set(index.nodes)
    for node in tree.iter():
        if node not in current and isinstance(node.tag, str):
            _collect(node, outside)
    index.excluded = set(outside.targets)
    _audit_notes(tree, report)
    _audit_ranges(index, report)
    references = 0
    for node in index.nodes:
        if reference := _reference(node):
            references += 1
            _audit_reference(node, reference, index, report)
    report.facts[FactKeys.TEXT_REFERENCE_COUNT] = references
    for kind, key in (
        ("bookmark", FactKeys.TEXT_BOOKMARK_COUNT),
        ("note", FactKeys.TEXT_NOTE_COUNT),
    ):
        report.facts[key] = sum(
            len(owners) for (target_kind, _), owners in index.targets.items() if target_kind == kind
        )


def _collect(node: etree._Element, index: _Index) -> None:
    if identity := node.get(XML_ID):
        index.targets["link", identity].add(node)
    if (attribute := NAMED_TARGETS.get(str(node.tag))) and (name := node.get(attribute)):
        index.targets["link", name].add(node)
    for kind in ("bookmark", "reference-mark"):
        name = node.get(qn("text", "name")) or ""
        if node.tag in {qn("text", kind), qn("text", kind + "-start")}:
            index.targets[kind, name].add(node)
            index.targets["link", name].add(node)
        elif node.tag == qn("text", kind + "-end"):
            index.ends[kind, name].append(node)
    if node.tag == qn("text", "note"):
        index.targets["note", node.get(qn("text", "id")) or ""].add(node)


def _audit_ranges(index: _Index, report: Report) -> None:
    for key, owners in index.targets.items():
        if key[0] not in {"bookmark", "reference-mark"}:
            continue
        for owner in owners:
            paired = index.ends.get(key, [])
            if not key[1] or len(owners) != 1 or not _valid_range(owner, paired, index):
                report.add(rules.REFERENCE003, location=index.locations[owner])
    for key, markers in index.ends.items():
        if key not in index.targets:
            for marker in markers:
                report.add(rules.REFERENCE003, location=index.locations[marker])


def _valid_range(owner: etree._Element, ends: list[etree._Element], index: _Index) -> bool:
    if not str(owner.tag).endswith("-start"):
        return not ends
    return (
        len(ends) == 1
        and index.positions[ends[0]] > index.positions[owner]
        and reading_context_path(ends[0]) == reading_context_path(owner)
    )


def _reference(node: etree._Element) -> tuple[str, str] | None:
    if kind := FIELDS.get(str(node.tag)):
        return kind, node.get(qn("text", "ref-name")) or ""
    href = node.get(qn("xlink", "href"), "")
    if node.tag in LINKS and href.startswith("#") and len(href) > 1:
        return "link", unquote(href[1:])
    return None


def _audit_reference(
    node: etree._Element, reference: tuple[str, str], index: _Index, report: Report
) -> None:
    kind, name = reference
    owners = index.targets.get(reference, set())
    if reference in index.excluded:
        report.add(
            rules.REFERENCE004,
            "A matching destination lies outside established current reading flow.",
            location=index.locations[node],
            details={"target": name, "target_kind": kind},
        )
        return
    if len(owners) != 1:
        rule = (
            rules.REFERENCE002
            if owners
            else (rules.REFERENCE004 if kind == "link" and "|" in name else rules.REFERENCE001)
        )
        report.add(
            rule,
            location=index.locations[node],
            details={
                "target": name,
                "target_kind": kind,
                "native_editing": (
                    "Review the intended destination in Writer; no retargeting is inferred."
                ),
            },
        )
    elif kind == "note":
        owner = next(iter(owners))
        if node.get(qn("text", "note-class")) not in {None, owner.get(qn("text", "note-class"))}:
            report.add(
                rules.NOTE002,
                "Note reference class differs from its destination.",
                location=index.locations[node],
            )


def _note(node: etree._Element, location: Location, report: Report) -> None:
    citations = list(node.iterchildren(qn("text", "note-citation")))
    bodies = list(node.iterchildren(qn("text", "note-body")))
    complete = len(citations) == 1 and len(bodies) == 1
    if not node.get(qn("text", "id")) or not complete or not visible_words(bodies[0]):
        report.add(rules.NOTE002, location=location)


def _audit_notes(tree: etree._ElementTree, report: Report) -> None:
    notes = text_nodes(tree, qn("text", "note"))
    if not notes:
        return
    identities = Counter(note.get(qn("text", "id")) for note in notes)
    classes: dict[str, int] = {}
    for note in notes:
        identity = note.get(qn("text", "id"))
        if identity and identities[identity] > 1:
            report.add(
                rules.NOTE002,
                "Note identity is duplicated.",
                location=Location.named(reading_context_path(note), "note", identity),
            )
        cls = note.get(qn("text", "note-class")) or "unknown"
        classes[cls] = classes.get(cls, 0) + 1
    report.add(
        rules.NOTE001,
        (
            "Footnotes/endnotes are present; verify their reading order "
            "and PDF/UA export behaviour manually."
        ),
        location=Location(Part.CONTENT.value),
        details={"count": len(notes), "classes": classes},
    )
