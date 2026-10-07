# SPDX-License-Identifier: MPL-2.0
"""Correlate link annotations with the Link structure elements that should represent them."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pypdf.errors import PdfReadError
from pypdf.generic import ArrayObject, IndirectObject

from odfa11y.report import rules

from .structure_walk import pdf_dictionary

if TYPE_CHECKING:
    from pypdf import PdfReader

    from odfa11y.report import Report

    from .structure_walk import StructureNode

MAX_LISTED = 20


@dataclass(frozen=True, slots=True)
class LinkAnnotation:
    """A ``/Link`` annotation with its object number and page."""

    xref: int | None
    page_xref: int | None
    page_number: int

    def describe(self) -> dict[str, int | None]:
        """Identify the annotation in a finding.

        Returns
        -------
        dict[str, int | None]
            The page number and the annotation's object number.

        """
        return {"page": self.page_number, "xref": self.xref}


def link_annotations(reader: PdfReader) -> list[LinkAnnotation]:
    """List every link annotation of every page.

    Returns
    -------
    list[LinkAnnotation]
        The annotations in page order; ``xref`` is None for a direct (unreferenceable) one.

    """
    found = []
    for number, page in enumerate(reader.pages, start=1):
        page_ref = page.indirect_reference
        raw = page.get("/Annots")
        items = raw.get_object() if raw is not None else None
        if not isinstance(items, ArrayObject):
            continue
        found.extend(
            LinkAnnotation(
                item.idnum if isinstance(item, IndirectObject) else None,
                page_ref.idnum if page_ref is not None else None,
                number,
            )
            for item in items
            if _is_link(item)
        )
    return found


def _is_link(item: object) -> bool:
    try:
        return pdf_dictionary(item).get("/Subtype") == "/Link"
    except PdfReadError:
        return False  # a malformed annotation entry is not a link we can correlate


def check_link_structure(
    annotations: list[LinkAnnotation], nodes: list[StructureNode], report: Report
) -> None:
    """Report links whose annotations and structure elements do not correspond.

    Findings: annotations without a Link element, Link elements without an annotation, and
    annotations referenced from another page. Several Link elements on the annotation's own
    page may share it: LibreOffice emits one per line of a wrapped link. The check claims only
    this correspondence; veraPDF remains the validator.
    """
    link_nodes = [node for node in nodes if node.role == "Link"]
    known = {a.xref for a in annotations if a.xref is not None}
    mapped: dict[int, list[int | None]] = defaultdict(list)
    for node in link_nodes:
        for reference in node.object_references:
            if reference.object_xref in known and reference.object_xref is not None:
                mapped[reference.object_xref].append(reference.page_xref)
    report.metadata["link_annotations"] = len(annotations)
    report.metadata["link_structure_elements"] = len(link_nodes)
    unmatched = [a for a in annotations if a.xref is None or a.xref not in mapped]
    if unmatched:
        report.add(
            rules.PDF016,
            details={
                "count": len(unmatched),
                "annotations": [a.describe() for a in unmatched[:MAX_LISTED]],
            },
        )
    orphans = [
        n for n in link_nodes if not any(r.object_xref in known for r in n.object_references)
    ]
    if orphans:
        report.add(
            rules.PDF017,
            details={
                "count": len(orphans),
                "page_xrefs": [n.page_xref for n in orphans[:MAX_LISTED]],
            },
        )
    conflicts = [
        a
        for a in annotations
        if a.xref in mapped and any(p not in {None, a.page_xref} for p in mapped[a.xref])
    ]
    if conflicts:
        report.add(
            rules.PDF018,
            details={
                "count": len(conflicts),
                "annotations": [a.describe() for a in conflicts[:MAX_LISTED]],
            },
        )
