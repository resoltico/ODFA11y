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

from .sheets import sheet_name, sheets

if TYPE_CHECKING:
    from collections.abc import Mapping

    from odfa11y.odf import OdfDocument

FORBIDDEN_CHARACTERS = frozenset("[]*?:/\\")
DYNAMIC_REFERENCE = re.compile(r"\b(?:INDIRECT|ADDRESS|HYPERLINK)\s*\(", re.IGNORECASE)
CONFIG = "{urn:oasis:names:tc:opendocument:xmlns:config:1.0}"
EMBEDDED_OBJECTS = "//office:body//draw:object | //office:body//draw:object-ole"


@dataclass(frozen=True, slots=True)
class SetSheetNames(Operation):
    """Rename sheets from an explicit mapping of current name to new name.

    Every rename is checked before the first edit. An unknown sheet, an invalid or
    colliding new name, and a sheet that formulas, ranges or links refer to by name all fail
    the operation and nothing is written. Renames are independent: a new name may not be
    another entry's current name, so chains and swaps are refused, and applying the mapping
    to its own result changes nothing.
    """

    entries: Mapping[str, str]
    name: ClassVar[str] = "set_sheet_names"
    family: ClassVar[Family | None] = Family.SPREADSHEET

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        found = {sheet_name(sheet): sheet for sheet in sheets(document.tree(Part.CONTENT))}
        names = Counter(sheet_name(sheet) for sheet in sheets(document.tree(Part.CONTENT)))
        failures = {
            old: problem
            for old, new in self.entries.items()
            if (
                problem := self._plan_problem(old, new)
                or _document_problem(document, old, new, names)
            )
        }
        if failures:
            return tuple(
                Outcome(self.name, Status.FAILED, message, key=old)
                for old, message in failures.items()
            )
        outcomes = []
        for old, new in self.entries.items():
            if names[old] == 0 or old == new:
                message = f"A sheet is already named {new!r}."
                outcomes.append(Outcome(self.name, Status.UNCHANGED, message, key=old))
                continue
            document.edit(Part.CONTENT)
            found[old].set(qn("table", "name"), new)
            _rename_settings(document, old, new)
            message = f"Renamed to {new!r}."
            outcomes.append(Outcome(self.name, Status.APPLIED, message, key=old, count=1))
        return tuple(outcomes)

    def _plan_problem(self, old: str, new: str) -> str | None:
        """Find what is wrong with an entry regardless of the document.

        Returns
        -------
        str | None
            The reason, or None when the entry is consistent with the rest of the plan.

        """
        reason = invalid_name_reason(new)
        if reason:
            return f"{new!r} is not a usable sheet name: {reason}."
        others = {key.casefold() for key in self.entries if key != old}
        if new.casefold() in others:
            return f"{new!r} is also renamed by this plan; chained and swapped renames are refused."
        if sum(target.casefold() == new.casefold() for target in self.entries.values()) > 1:
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
    if names[old] == 0:
        return None if names[new] == 1 else f"No unique sheet is named {old!r} or {new!r}."
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
            document.edit(Part.SETTINGS)
            entry.set(f"{CONFIG}name", new)
    for item in document.tree(Part.SETTINGS).iter(f"{CONFIG}config-item"):
        if item.get(f"{CONFIG}name") == "ActiveTable" and item.text == old:
            document.edit(Part.SETTINGS)
            item.text = new
