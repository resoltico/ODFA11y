# SPDX-License-Identifier: MPL-2.0
"""Inspect list membership, counter relationships and manually simulated list cues."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import TYPE_CHECKING

from odfa11y.content import reading_context_path, visible_words
from odfa11y.families.text.contexts import text_nodes
from odfa11y.odf import Part, qn
from odfa11y.report import FactKeys, Location, rules

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report

XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
LIST = qn("text", "list")
ITEM = qn("text", "list-item")
HEADER = qn("text", "list-header")
COUNTER_BOUNDARIES = frozenset({
    qn("table", "table-cell"),
    qn("table", "covered-table-cell"),
    qn("draw", "text-box"),
})
TYPED_MARKER = re.compile(r"^\s*(?:[•◦▪‣*-]|\(?\d{1,3}[.)]|[A-Za-z][.)])\s+\S")


def list_level(node: etree._Element) -> int:
    """Resolve the counter level, resetting at table cells and text boxes.

    Returns
    -------
    int
        One-based list level within its counter domain.

    """
    level = 1
    for ancestor in node.iterancestors():
        if ancestor.tag in COUNTER_BOUNDARIES:
            break
        level += int(ancestor.tag == LIST)
    return level


def audit_lists(document: OdfDocument, report: Report) -> None:
    """Report relationships without performing typography-based rewrites."""
    tree = document.tree(Part.CONTENT)
    available = text_nodes(tree, LIST)
    locations = {}
    counters: Counter[str] = Counter()
    by_id: dict[str, list[etree._Element]] = defaultdict(list)
    ids = Counter(identity for node in tree.iter() if (identity := node.get(XML_ID)))
    for node in available:
        context = reading_context_path(node)
        counters[context] += 1
        locations[node] = Location.indexed(context, "list", counters[context])
        if identity := node.get(XML_ID):
            by_id[identity].append(node)
            if ids[identity] > 1:
                report.add(
                    rules.LIST001, "List XML identity is duplicated.", location=locations[node]
                )
        _membership(node, locations[node], report)
    edges = _continuations(available, by_id, ids, locations, report)
    for node in _cycles(edges):
        report.add(
            rules.LIST002,
            "List continuation participates in a counter cycle.",
            location=locations[node],
        )
    simulated = 0
    for index, node in enumerate(text_nodes(tree, qn("text", "p")), 1):
        if not any(parent.tag == LIST for parent in node.iterancestors()) and TYPED_MARKER.match(
            visible_words(node)
        ):
            simulated += 1
            report.add(
                rules.LIST004,
                location=Location.indexed(reading_context_path(node), "paragraph", index),
                details={
                    "native_editing": (
                        "Review and author a real list in Writer; "
                        "automatic typography rewrites are refused."
                    )
                },
            )
    report.facts[FactKeys.TEXT_LIST_COUNT] = len(available)
    report.facts[FactKeys.TEXT_LIST_MAX_LEVEL] = max(
        (list_level(node) for node in available), default=0
    )
    report.facts[FactKeys.TEXT_LIST_CONTINUATION_COUNT] = len(edges)
    report.facts[FactKeys.TEXT_SIMULATED_LIST_COUNT] = simulated


def _membership(node: etree._Element, location: Location, report: Report) -> None:
    children = [child for child in node if isinstance(child.tag, str)]
    invalid = any(child.tag not in {ITEM, HEADER} for child in children)
    headers = [child for child in children if child.tag == HEADER]
    if invalid or len(headers) > 1 or (headers and children[0] is not headers[0]):
        report.add(rules.LIST001, location=location)
    parent = node.getparent()
    if parent is not None and parent.tag == LIST:
        report.add(
            rules.LIST001, "A nested list must belong to a list item or header.", location=location
        )
    if node.get(qn("text", "continue-numbering")) not in {None, "true", "false", "1", "0"}:
        report.add(
            rules.LIST001,
            "List continuation has an invalid boolean declaration.",
            location=location,
        )


def _continuations(
    available: list[etree._Element],
    by_id: dict[str, list[etree._Element]],
    ids: Counter[str],
    locations: dict[etree._Element, Location],
    report: Report,
) -> dict[etree._Element, etree._Element]:
    edges = {}
    preceding = {}
    for node in available:
        key = (_domain(node), list_level(node), _style(node))
        reference = node.get(qn("text", "continue-list"))
        if reference:
            targets = by_id.get(reference, [])
            if len(targets) != 1 or ids[reference] != 1:
                report.add(
                    rules.LIST002,
                    "List continuation target is missing or ambiguous.",
                    location=locations[node],
                    details={"reference": reference},
                )
            else:
                edges[node] = targets[0]
                if _domain(targets[0]) != _domain(node) or list_level(targets[0]) != list_level(
                    node
                ):
                    report.add(
                        rules.LIST003,
                        "List continuation crosses a reading or counter domain.",
                        location=locations[node],
                    )
        elif node.get(qn("text", "continue-numbering")) in {"true", "1"}:
            if key not in preceding or key[-1] is None:
                report.add(rules.LIST003, location=locations[node])
            else:
                edges[node] = preceding[key]
        preceding[key] = node
    return edges


def _cycles(edges: dict[etree._Element, etree._Element]) -> set[etree._Element]:
    finished = set()
    found = set()
    for start in edges:
        path = {}
        node = start
        while node in edges and node not in finished:
            if node in path:
                found.update(list(path)[path[node] :])
                break
            path[node] = len(path)
            node = edges[node]
        finished.update(path)
    return found


def _domain(node: etree._Element) -> tuple[str, etree._Element | None]:
    boundary = next(
        (parent for parent in node.iterancestors() if parent.tag in COUNTER_BOUNDARIES), None
    )
    return reading_context_path(node), boundary


def _style(node: etree._Element) -> str | None:
    for candidate in [node, *node.iterancestors()]:
        if candidate.tag in COUNTER_BOUNDARIES:
            break
        if candidate.tag == LIST and (name := candidate.get(qn("text", "style-name"))):
            return name
    return None
