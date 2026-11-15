# SPDX-License-Identifier: MPL-2.0
"""Rename sheets, refusing any rename that could break a reference to the old name."""

import re
from collections import Counter
from urllib.parse import unquote

from odfa11y.decisions import Decision
from odfa11y.decisions.domain import resolved_node
from odfa11y.decisions.edit import Outcome, Status
from odfa11y.errors import DocumentRefusal
from odfa11y.families.spreadsheet.answers import SheetNameAnswer
from odfa11y.families.spreadsheet.sheets import sheet_name, sheets
from odfa11y.odf import PackageStorage, Part, select_elements
from odfa11y.odf import names as xml_names
lazy from odfa11y.odf import OdfDocument

DYNAMIC_REFERENCE = re.compile(r"\b(?:INDIRECT|ADDRESS|HYPERLINK)\s*\(", re.IGNORECASE)
CONFIG = xml_names.CONFIG_NAMESPACE
EMBEDDED_OBJECTS = "//office:body//draw:object | //office:body//draw:object-ole"


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
    own_name = xml_names.TABLE_NAME
    sheet_tag = xml_names.TABLE_TABLE
    for tree in document.distinct_trees(Part.CONTENT, Part.STYLES):
        for element in tree.iter("*"):
            for attribute, value in element.attrib.items():
                if attribute == own_name and element.tag == sheet_tag:
                    continue
                if attribute == xml_names.TABLE_FORMULA and DYNAMIC_REFERENCE.search(value):
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


def edit_sheet_name(
    document: OdfDocument, decision: Decision[SheetNameAnswer]
) -> tuple[Outcome, ...]:
    """Rename one sheet after establishing that references and settings can be preserved."""
    node = resolved_node(document, decision)
    old = sheet_name(node)
    new = decision.answer.name
    names = Counter(sheet_name(sheet) for sheet in sheets(document.tree(Part.CONTENT)))
    if problem := _document_problem(document, old, new, names):
        raise DocumentRefusal(problem)
    changed = old != new
    if changed:
        node.set(xml_names.TABLE_NAME, new)
        _rename_settings(document, old, new)
    return (
        Outcome(
            decision.kind.id,
            Status.APPLIED if changed else Status.UNCHANGED,
            f"Renamed to {new!r}." if changed else f"Sheet is already named {new!r}.",
            target=decision.target_path,
            count=int(changed),
        ),
    )
