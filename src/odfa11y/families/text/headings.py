# SPDX-License-Identifier: MPL-2.0
"""Reviewed, explicit semantic heading levels with stable logical targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override
from urllib.parse import quote

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.content import protected_xml
from odfa11y.odf import Family, Part, qn, select_elements
from odfa11y.report import Location

if TYPE_CHECKING:
    from collections.abc import Mapping

    from lxml import etree

    from odfa11y.odf import OdfDocument

MAX_HEADING_LEVEL = 10
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


@dataclass(frozen=True, slots=True)
class HeadingLevel:
    """One chosen outline level and the reviewed heading fingerprint."""

    level: int
    fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class SetHeadingLevels(Operation):
    """Resolve all heading decisions before changing any outline-level attribute."""

    entries: Mapping[str, HeadingLevel]
    name: ClassVar[str] = "set_heading_levels"
    family: ClassVar[Family | None] = Family.TEXT

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        headings = select_elements(document.tree(Part.CONTENT), "//office:body//text:h")
        targets: dict[str, list[etree._Element]] = {}
        for index, heading in enumerate(headings, start=1):
            targets.setdefault(heading_location(heading, index).path, []).append(heading)
        decisions = []
        failures = []
        for target, entry in self.entries.items():
            matches = targets.get(target, [])
            problem = _problem(target, entry, matches)
            if problem:
                failures.append(Outcome(self.name, Status.FAILED, problem, key=target))
            else:
                decisions.append((target, matches[0], entry.level))
        if failures:
            return tuple(failures)
        outcomes = []
        for target, heading, level in decisions:
            changed = heading.get(qn("text", "outline-level")) != str(level)
            if changed:
                document.edit(Part.CONTENT)
                heading.set(qn("text", "outline-level"), str(level))
            outcomes.append(
                Outcome(
                    self.name,
                    Status.APPLIED if changed else Status.UNCHANGED,
                    f"Outline level {level}.",
                    key=target,
                    count=int(changed),
                )
            )
        return tuple(outcomes)


def heading_location(heading: etree._Element, index: int) -> Location:
    """Address a heading by XML identity, otherwise by its one-based ordinal.

    Returns
    -------
    Location
        The canonical logical heading target.

    """
    identity = heading.get(XML_ID)
    return (
        Location(f"{Part.CONTENT}/heading[id={quote(identity, safe='')}]")
        if identity
        else Location.indexed(Part.CONTENT, "heading", index)
    )


def heading_fingerprint(heading: etree._Element) -> str:
    """Bind an outline decision to the full heading content, excluding mutable metadata.

    Returns
    -------
    str
        The stable reviewed-content digest.

    """
    return protected_xml(
        heading,
        omitted_root_attributes=(qn("text", "outline-level"),),
        omitted_elements=(qn("svg", "title"), qn("svg", "desc")),
    )[:16]


def _problem(target: str, entry: HeadingLevel, matches: list[etree._Element]) -> str | None:
    if len(matches) != 1:
        return "The heading target must resolve to exactly one heading."
    if type(entry.level) is not int or not 1 <= entry.level <= MAX_HEADING_LEVEL:
        return "An outline level must be an integer from 1 to 10."
    if "[id=" not in target and entry.fingerprint is None:
        return "An ordinal heading target requires its reviewed fingerprint."
    if entry.fingerprint is not None and entry.fingerprint != heading_fingerprint(matches[0]):
        return "The heading is no longer the object this plan was reviewed against."
    return None
