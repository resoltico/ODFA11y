# SPDX-License-Identifier: MPL-2.0
"""Correlate link annotations with the Link structure elements that should represent them."""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Annotated, Literal

from pypdf.errors import PdfReadError
from pypdf.generic import ArrayObject
lazy from pypdf.generic import DictionaryObject

from odfa11y.contracts import Description
from odfa11y.pdf.reading.objects import dictionary, has_text, text, xref
from odfa11y.rules import registry as rules
from odfa11y.rules.details import DETAIL_ITEMS
lazy from odfa11y.pdf.reading import BoundedPdf
lazy from odfa11y.pdf.reading.structure import StructureNode
lazy from odfa11y.report import Report


@dataclass(frozen=True, slots=True)
class PdfLinkMeasurements:
    """Measurements produced by pdf-links analysis; None denotes unmeasured data."""

    producer: Literal["pdf-links"] = field(default="pdf-links", init=False)
    link_annotation_count: Annotated[int | None, Description("Inspected link annotations.")] = None
    link_structure_element_count: Annotated[
        int | None, Description("Link elements in the structure tree.")
    ] = None


@dataclass(frozen=True, slots=True)
class LinkAnnotation:
    """A ``/Link`` annotation with its object number and page."""

    xref: int | None
    page_xref: int | None
    page_number: int
    description: str | None

    @property
    def has_description(self) -> bool:
        return has_text(self.description)

    def describe(self) -> dict[str, int | None]:
        """Identify the annotation in a finding.

        Returns
        -------
        dict[str, int | None]
            The page number and the annotation's object number.

        """
        return {"page": self.page_number, "xref": self.xref}


def link_annotations(reader: BoundedPdf) -> list[LinkAnnotation]:
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
        for item in items:
            annotation = _link_dictionary(item)
            if annotation is not None:
                found.append(
                    LinkAnnotation(
                        xref(item),
                        xref(page_ref),
                        number,
                        text(annotation.get("/Contents")),
                    )
                )
    return found


def _link_dictionary(item: object) -> DictionaryObject | None:
    try:
        annotation = dictionary(item)
    except PdfReadError:
        return None  # a malformed annotation entry is not a link we can correlate
    return annotation if annotation.get("/Subtype") == "/Link" else None


def check_link_structure(
    annotations: list[LinkAnnotation], nodes: list[StructureNode], report: Report
) -> None:
    """Report links whose annotations and structure elements do not correspond.

    Findings: annotations without a Link element, Link elements without an annotation,
    annotations referenced from another page, and links with no alternate description (the
    annotation's ``/Contents`` or the ``/Alt`` of a Link element that refers to it). Several
    Link elements on the annotation's own page may share it: LibreOffice emits one per line of
    a wrapped link. The check claims only these correspondences; veraPDF remains the validator.
    """
    link_nodes = [node for node in nodes if node.role == "Link"]
    known = {a.xref for a in annotations if a.xref is not None}
    mapped: dict[int, list[int | None]] = defaultdict(list)
    alternates: set[int] = set()
    for node in link_nodes:
        for reference in node.object_references:
            if reference.object_xref in known and reference.object_xref is not None:
                mapped[reference.object_xref].append(reference.page_xref)
                if has_text(node.element.get("/Alt")):
                    alternates.add(reference.object_xref)
    report.measure(PdfLinkMeasurements(link_annotation_count=len(annotations)))
    report.measure(PdfLinkMeasurements(link_structure_element_count=len(link_nodes)))
    unmatched = [a for a in annotations if a.xref is None or a.xref not in mapped]
    if unmatched:
        report.raise_(
            rules.PDF017,
            details={
                "count": len(unmatched),
                "annotations": [a.describe() for a in unmatched[:DETAIL_ITEMS]],
            },
        )
    orphans = [
        n for n in link_nodes if not any(r.object_xref in known for r in n.object_references)
    ]
    if orphans:
        report.raise_(
            rules.PDF018,
            details={
                "count": len(orphans),
                "page_xrefs": [n.page_xref for n in orphans[:DETAIL_ITEMS]],
            },
        )
    conflicts = [
        a
        for a in annotations
        if a.xref in mapped and any(p not in {None, a.page_xref} for p in mapped[a.xref])
    ]
    if conflicts:
        report.raise_(
            rules.PDF019,
            details={
                "count": len(conflicts),
                "annotations": [a.describe() for a in conflicts[:DETAIL_ITEMS]],
            },
        )
    undescribed = [a for a in annotations if not a.has_description and a.xref not in alternates]
    if undescribed:
        report.raise_(
            rules.PDF020,
            details={
                "count": len(undescribed),
                "annotations": [a.describe() for a in undescribed[:DETAIL_ITEMS]],
            },
        )
