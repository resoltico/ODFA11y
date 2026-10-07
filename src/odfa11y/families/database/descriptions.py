# SPDX-License-Identifier: MPL-2.0
"""Describe declared database objects without opening connections or changing bindings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.content import protected_xml
from odfa11y.odf import Family, Part, qn, select_elements
from odfa11y.report import Location

if TYPE_CHECKING:
    from collections.abc import Mapping

    from lxml import etree

    from odfa11y.odf import OdfDocument

OBJECTS = {
    qn("db", name)
    for name in (
        "query",
        "query-collection",
        "component",
        "component-collection",
        "column",
        "table-representation",
    )
}
ORDINAL = re.compile(r"\[[0-9]+\]")


def targets(document: OdfDocument) -> dict[str, list[etree._Element]]:
    """Index described objects by hierarchical logical name/ordinal paths.

    Returns
    -------
    dict[str, list[etree._Element]]
        Every declaration for each target; duplicates remain visible for rejection.

    """
    result: dict[str, list[etree._Element]] = {}
    positions: dict[etree._Element, dict[etree._Element, int]] = {}
    roots = select_elements(document.tree(Part.CONTENT), "//office:body/office:database")
    if not roots:
        return result
    for node in roots[0].iter():
        if node.tag in OBJECTS or _form_target(node):
            result.setdefault(_path(node, positions), []).append(node)
    return result


def description_attribute(node: etree._Element) -> str:
    """Choose the standard description field for one declared object.

    Returns
    -------
    str
        ``db:description`` or a form control's ``form:title``.

    """
    return qn("form", "title") if _form_target(node) else qn("db", "description")


def fingerprint(node: etree._Element) -> str:
    """Bind the description decision to SQL, bindings and all other object content.

    Returns
    -------
    str
        A reviewed digest excluding only the object's description.

    """
    return protected_xml(node, omitted_element_attributes=description_attributes(node))[:16]


def description_attributes(root: etree._Element) -> dict[str, tuple[str, ...]]:
    """Declare precisely the editable description attributes within a target subtree.

    Returns
    -------
    dict[str, tuple[str, ...]]
        Standard object attributes, including independently described descendants.

    """
    attributes: dict[str, tuple[str, ...]] = {tag: (qn("db", "description"),) for tag in OBJECTS}
    for node in root.iter():
        if _form_target(node):
            attributes[str(node.tag)] = (qn("form", "title"),)
    return attributes


def _form_target(node: etree._Element) -> bool:
    return (
        isinstance(node.tag, str)
        and node.tag.startswith(qn("form", ""))
        and bool(node.get(qn("form", "name")))
    )


def _path(node: etree._Element, positions: dict[etree._Element, dict[etree._Element, int]]) -> str:
    parts = []
    for item in reversed([node, *node.iterancestors()]):
        if item.tag not in OBJECTS and not _form_target(item):
            continue
        kind = str(item.tag).rpartition("}")[2]
        name = item.get(qn("db", "name")) or item.get(qn("form", "name"))
        segment = (
            Location.named("content", kind, name).path
            if name
            else Location.indexed("content", kind, _ordinal(item, positions)).path
        )
        parts.append(segment.removeprefix("content/"))
    return "content/" + "/".join(parts)


def _ordinal(
    node: etree._Element, positions: dict[etree._Element, dict[etree._Element, int]]
) -> int:
    parent = node.getparent()
    if parent is None:
        return 1
    if parent not in positions:
        counts: dict[object, int] = {}
        siblings = {}
        for child in parent:
            counts[child.tag] = counts.get(child.tag, 0) + 1
            siblings[child] = counts[child.tag]
        positions[parent] = siblings
    return positions[parent][node]


@dataclass(frozen=True, slots=True)
class DatabaseDescription:
    """One supplied description and its optional reviewed object identity."""

    text: str
    fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class SetObjectDescriptions(Operation):
    """Preflight descriptions for all declared objects before editing any field."""

    entries: Mapping[str, DatabaseDescription]
    name: ClassVar[str] = "set_object_descriptions"
    family: ClassVar[Family | None] = Family.DATABASE

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        available = targets(document)
        decisions = []
        failures = []
        for target, value in self.entries.items():
            matches = available.get(target, [])
            problem = _problem(target, matches, value)
            if problem:
                failures.append(Outcome(self.name, Status.FAILED, problem, key=target))
            else:
                decisions.append((target, matches[0], value.text.strip()))
        if failures:
            return tuple(failures)
        outcomes = []
        for target, node, text in decisions:
            attribute = description_attribute(node)
            changed = node.get(attribute) != text
            if changed:
                document.edit(Part.CONTENT)
                node.set(attribute, text)
            outcomes.append(
                Outcome(
                    self.name,
                    Status.APPLIED if changed else Status.UNCHANGED,
                    "Set supplied database object description."
                    if changed
                    else "Database object description already matches.",
                    key=target,
                    count=int(changed),
                )
            )
        return tuple(outcomes)


def _problem(target: str, matches: list[etree._Element], value: DatabaseDescription) -> str | None:
    if len(matches) != 1:
        return "A database object target must resolve to exactly one declaration."
    if not isinstance(value.text, str) or not value.text.strip():
        return "A database description must be a nonblank string."
    if ORDINAL.search(target) and value.fingerprint is None:
        return "An ordinal database target requires its reviewed fingerprint."
    if value.fingerprint is not None and value.fingerprint != fingerprint(matches[0]):
        return "The database object changed since the plan was reviewed."
    return None
