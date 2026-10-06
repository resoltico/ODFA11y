# SPDX-License-Identifier: MPL-2.0
"""Inspect the reachable PDF structure tree and resolve custom roles."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from pypdf.errors import PdfReadError
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, NameObject

from .models import Severity

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .models import AuditReport

STANDARD_STRUCTURE_TYPES = {
    "Document",
    "Part",
    "Art",
    "Sect",
    "Div",
    "BlockQuote",
    "Caption",
    "TOC",
    "TOCI",
    "Index",
    "NonStruct",
    "Private",
    "P",
    "H",
    "H1",
    "H2",
    "H3",
    "H4",
    "H5",
    "H6",
    "L",
    "LI",
    "Lbl",
    "LBody",
    "Table",
    "TR",
    "TH",
    "TD",
    "THead",
    "TBody",
    "TFoot",
    "Span",
    "Quote",
    "Note",
    "Reference",
    "BibEntry",
    "Code",
    "Link",
    "Annot",
    "Ruby",
    "Warichu",
    "Figure",
    "Formula",
    "Form",
}


def pdf_dictionary(value: object) -> DictionaryObject:
    """Resolve an optional direct or indirect PDF dictionary.

    Returns
    -------
    DictionaryObject
        The resolved dictionary, or an empty dictionary when the value is absent.

    Raises
    ------
    PdfReadError
        A present value is not a dictionary.

    """
    if isinstance(value, IndirectObject):
        value = value.get_object()
    if value is None:
        return DictionaryObject()
    if not isinstance(value, DictionaryObject):
        msg = "Expected a PDF dictionary"
        raise PdfReadError(msg)
    return value


def audit_structure(root: DictionaryObject, report: AuditReport) -> None:
    """Record structure tags, unmapped roles and missing figure descriptions."""
    role_map = {
        str(key).removeprefix("/"): str(value).removeprefix("/")
        for key, value in pdf_dictionary(root.get("/RoleMap")).items()
    }
    counts: Counter[str] = Counter()
    figures: list[int] = []
    missing_alt: list[int] = []
    for element in _walk_structure(root):
        tag = element.get("/S")
        if not isinstance(tag, NameObject):
            continue
        name = str(tag).removeprefix("/")
        counts[name] += 1
        if _resolve_role(name, role_map) == "Figure":
            reference = element.indirect_reference
            xref = reference.idnum if reference is not None else 0
            figures.append(xref)
            alt = element.get("/Alt")
            if not isinstance(alt, str) or not alt.strip():
                missing_alt.append(xref)
    report.metadata["structure_tags"] = dict(sorted(counts.items()))
    if role_map:
        report.metadata["role_map"] = dict(sorted(role_map.items()))
    _report_structure_findings(counts, role_map, figures, missing_alt, report)


def _report_structure_findings(
    counts: Counter[str],
    role_map: dict[str, str],
    figures: list[int],
    missing_alt: list[int],
    report: AuditReport,
) -> None:
    unmapped = sorted(name for name in counts if _resolve_role(name, role_map) is None)
    if unmapped:
        report.add(
            "PDF011",
            Severity.ERROR,
            "Custom structure types do not resolve to standard types through /RoleMap.",
            details={"unmapped_structure_types": unmapped},
        )
    if missing_alt:
        report.add(
            "PDF007",
            Severity.ERROR,
            "One or more Figure structure elements have no /Alt text.",
            details={"figure_xrefs": figures, "missing_alt_xrefs": missing_alt},
        )
    resolved = {_resolve_role(name, role_map) for name in counts}
    if not any(name and name.startswith("H") and name[1:].isdigit() for name in resolved):
        report.add("PDF008", Severity.INFO, "No PDF heading structure tags were detected.")


def _walk_structure(root: DictionaryObject) -> Iterator[DictionaryObject]:
    pending: list[object] = [root]
    seen: set[int] = set()
    while pending:
        value = pending.pop()
        if isinstance(value, IndirectObject):
            value = value.get_object()
        if isinstance(value, ArrayObject | DictionaryObject):
            if id(value) in seen:
                continue
            seen.add(id(value))
        if isinstance(value, ArrayObject):
            pending.extend(reversed(value))
        elif isinstance(value, DictionaryObject):
            yield value
            if "/K" in value:
                pending.append(value.get("/K"))


def _resolve_role(name: str, role_map: dict[str, str]) -> str | None:
    seen: set[str] = set()
    while name not in STANDARD_STRUCTURE_TYPES:
        if name in seen or name not in role_map:
            return None
        seen.add(name)
        name = role_map[name]
    return name
