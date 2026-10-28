# SPDX-License-Identifier: MPL-2.0
"""Rename sheets, refusing any rename that could break a reference to the old name."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override
from urllib.parse import unquote

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.odf import Family, PackageStorage, Part, qn, select_elements
from odfa11y.report import Location

from .sheets import sheet_name, sheets
from .snapshot import sheet_fingerprint

if TYPE_CHECKING:
    from collections.abc import Mapping

    from odfa11y.odf import OdfDocument

FORBIDDEN_CHARACTERS = frozenset("[]*?:/\\")
DYNAMIC_REFERENCE = re.compile(r"\b(?:INDIRECT|ADDRESS|HYPERLINK)\s*\(", re.IGNORECASE)
CONFIG = "{urn:oasis:names:tc:opendocument:xmlns:config:1.0}"
EMBEDDED_OBJECTS = "//office:body//draw:object | //office:body//draw:object-ole"


@dataclass(frozen=True, slots=True)
class SheetNameChange:
    """A reviewed name and preserved identity for one logical sheet target."""

    name: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class SetSheetNames(Operation):
    """Rename stable logical sheet targets without rewriting unestablished references."""

    entries: Mapping[str, SheetNameChange]
    name: ClassVar[str] = "set_sheet_names"
    families: ClassVar[frozenset[Family] | None] = frozenset({Family.SPREADSHEET})

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        available = list(sheets(document.tree(Part.CONTENT)))
        found = {
            Location.indexed(Part.CONTENT, "sheet", index).path: sheet
            for index, sheet in enumerate(available, 1)
        }
        names = Counter(sheet_name(sheet) for sheet in available)
        renames = {
            sheet_name(found[target]): entry.name
            for target, entry in self.entries.items()
            if target in found
        }
        failures = {}
        for target, entry in self.entries.items():
            node = found.get(target)
            if node is None:
                failures[target] = "The sheet target must resolve to exactly one sheet."
            elif entry.fingerprint != sheet_fingerprint(document, node):
                failures[target] = (
                    "The sheet is no longer the object this plan was reviewed against."
                )
            elif problem := self._plan_problem(
                sheet_name(node), entry.name, renames
            ) or _document_problem(document, sheet_name(node), entry.name, names):
                failures[target] = problem
        if failures:
            return tuple(
                Outcome(self.name, Status.FAILED, message, key=target)
                for target, message in failures.items()
            )
        outcomes = []
        for target, entry in self.entries.items():
            node = found[target]
            old = sheet_name(node)
            if old == entry.name:
                outcomes.append(
                    Outcome(
                        self.name,
                        Status.UNCHANGED,
                        f"Sheet is already named {entry.name!r}.",
                        key=target,
                    )
                )
            else:
                node.set(qn("table", "name"), entry.name)
                _rename_settings(document, old, entry.name)
                outcomes.append(
                    Outcome(
                        self.name,
                        Status.APPLIED,
                        f"Renamed to {entry.name!r}.",
                        key=target,
                        count=1,
                    )
                )
        return tuple(outcomes)

    @staticmethod
    def _plan_problem(old: str, new: str, renames: Mapping[str, str]) -> str | None:
        """Find what is wrong with an entry regardless of the document.

        Returns
        -------
        str | None
            The reason, or None when the entry is consistent with the rest of the plan.

        """
        reason = invalid_name_reason(new)
        if reason:
            return f"{new!r} is not a usable sheet name: {reason}."
        others = {key.casefold() for key in renames if key != old}
        if new.casefold() in others:
            return f"{new!r} is also renamed by this plan; chained and swapped renames are refused."
        if sum(target.casefold() == new.casefold() for target in renames.values()) > 1:
            return f"More than one sheet is renamed to {new!r}."
        return None


def invalid_name_reason(name: str) -> str | None:
    """Explain why a name cannot be a sheet name.

    Returns
    -------
    str | None
        The reason, or None for a usable name: not blank, free of square brackets, ``*``,
        ``?``, ``:``, ``/`` and backslash, and without an apostrophe at either end.

    """
    if not name.strip():
        return "it is empty"
    if FORBIDDEN_CHARACTERS & set(name):
        return "it contains one of [ ] * ? : / \\"
    if name.startswith("'") or name.endswith("'"):
        return "it starts or ends with an apostrophe"
    return None


def _document_problem(document: OdfDocument, old: str, new: str, names: Counter[str]) -> str | None:
    """Find what is wrong with an entry given the document's sheets.

    Returns
    -------
    str | None
        The reason, or None when the rename is safe or its result already holds.

    """
    if names[old] > 1:
        return f"{names[old]} sheets are named {old!r}; the name must be unique."
    if old == new:
        return None
    if any(name != old and name.casefold() == new.casefold() for name in names):
        return f"A sheet is already named {new!r}."
    return _reference_problem(document, old)


def _reference_problem(document: OdfDocument, old: str) -> str | None:
    if _has_scripts(document):
        return f"Cannot rename {old!r}: embedded scripts may refer to sheet names."
    if select_elements(document.tree(Part.CONTENT), EMBEDDED_OBJECTS):
        return (
            f"Cannot rename {old!r}: the document embeds charts or objects whose references "
            "to sheet names are not inspected."
        )
    if _is_referenced(document, old):
        return (
            f"Cannot rename {old!r}: a formula, range or link may refer to it by name, and "
            "references are not rewritten."
        )
    return None


def _is_referenced(document: OdfDocument, name: str) -> bool:
    """Whether any attribute of the content or styles may refer to a sheet by name.

    The test is deliberately conservative: it looks for the name followed by a dot, plain or
    quoted as a formula writes it, or a link to the bare name, so a sheet whose name ends
    another sheet's name may be reported as referenced.

    Returns
    -------
    bool
        True when a reference may exist.

    """
    quoted = "'" + name.replace("'", "''") + "'"
    dotted = (f"{name}.".casefold(), f"{quoted}.".casefold())
    links = {f"#{name}".casefold(), f"#{quoted}".casefold()}
    own_name = qn("table", "name")
    sheet_tag = qn("table", "table")
    for tree in document.distinct_trees(Part.CONTENT, Part.STYLES):
        for element in tree.iter("*"):
            for attribute, value in element.attrib.items():
                if attribute == own_name and element.tag == sheet_tag:
                    continue
                if attribute == qn("table", "formula") and DYNAMIC_REFERENCE.search(value):
                    return True
                reference = unquote(value).casefold()
                if reference in links or any(token in reference for token in dotted):
                    return True
    return False


def _has_scripts(document: OdfDocument) -> bool:
    for tree in document.distinct_trees(Part.CONTENT, Part.STYLES):
        if select_elements(tree, "//office:scripts/* | //office:event-listeners/*"):
            return True
    return isinstance(document.storage, PackageStorage) and any(
        name.lower().startswith(("basic/", "scripts/")) for name in document.storage.member_names()
    )


def _rename_settings(document: OdfDocument, old: str, new: str) -> None:
    if not document.has(Part.SETTINGS):
        return
    for entry in document.tree(Part.SETTINGS).iter(f"{CONFIG}config-item-map-entry"):
        parent = entry.getparent()
        if (
            parent is not None
            and parent.get(f"{CONFIG}name") in {"Tables", "ScriptConfiguration"}
            and entry.get(f"{CONFIG}name") == old
        ):
            entry.set(f"{CONFIG}name", new)
    for item in document.tree(Part.SETTINGS).iter(f"{CONFIG}config-item"):
        if item.get(f"{CONFIG}name") == "ActiveTable" and item.text == old:
            item.text = new
