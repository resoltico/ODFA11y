# SPDX-License-Identifier: MPL-2.0
"""Reconcile the marked content of each page with the structure tree that should own it."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import TYPE_CHECKING

from pypdf.generic import ArrayObject, NumberObject, StreamObject

from odfa11y.errors import ToolFailedError
from odfa11y.pdf_limits import MAX_CONTENT_BYTES
from odfa11y.report import rules

from .content_scan import scan_content
from .link_structure import MAX_LISTED
from .structure_walk import pdf_dictionary

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from pypdf import PageObject

    from odfa11y.report import Report

    from .structure_walk import StructureNode


def check_marked_content(
    pages: Iterable[PageObject], nodes: list[StructureNode], report: Report
) -> None:
    """Report page content that is not tagged, and structure references that match no content.

    Each page's content stream is scanned for marked-content sequences. Findings: MCIDs no
    structure element refers to (``PDF020``), references to MCIDs the page does not contain
    (``PDF021``), MCIDs referred to more than once (``PDF022``) and text shown outside tagged
    content and ``/Artifact`` (``PDF023``). Content of form XObjects is not scanned, so
    references into it (``/Stm``) are ignored. The check claims only these correspondences;
    veraPDF remains the validator. Decoded content beyond ``MAX_CONTENT_BYTES`` in all pages
    raises ``ToolFailedError``.
    """
    references: dict[int | None, Counter[int]] = defaultdict(Counter)
    for node in nodes:
        for reference in node.marked_content:
            references[reference.page_xref][reference.mcid] += 1
    budget = MAX_CONTENT_BYTES
    untagged: list[dict[str, int]] = []
    unreferenced: list[dict[str, object]] = []
    page_numbers: dict[int | None, int] = {}
    contents: dict[int, set[int]] = {}
    for number, page in enumerate(pages, start=1):
        data = _decoded_content(page, budget)
        budget -= len(data)
        scan = scan_content(data, _property_mcids(page))
        xref = page.indirect_reference.idnum if page.indirect_reference else None
        page_numbers[xref] = number
        contents[number] = scan.mcids
        loose = sorted(scan.mcids - set(references.get(xref, ())))
        if loose:
            unreferenced.append({"page": number, "count": len(loose), "mcids": loose[:MAX_LISTED]})
        if scan.unmarked_text_operations:
            untagged.append({"page": number, "text_operations": scan.unmarked_text_operations})
    report.metadata["marked_content_ids"] = sum(len(ids) for ids in contents.values())
    _report(report, unreferenced, untagged, _dangling(references, page_numbers, contents))
    duplicated = [
        {"page": page_numbers.get(xref), "mcid": mcid, "references": count}
        for xref, counts in references.items()
        for mcid, count in counts.items()
        if count > 1
    ]
    if duplicated:
        report.add(
            rules.PDF022, details={"count": len(duplicated), "mcids": duplicated[:MAX_LISTED]}
        )


def _report(
    report: Report,
    unreferenced: list[dict[str, object]],
    untagged: list[dict[str, int]],
    dangling: list[dict[str, int | None]],
) -> None:
    if unreferenced:
        report.add(rules.PDF020, details={"pages": unreferenced[:MAX_LISTED]})
    if dangling:
        report.add(
            rules.PDF021, details={"count": len(dangling), "references": dangling[:MAX_LISTED]}
        )
    if untagged:
        report.add(rules.PDF023, details={"pages": untagged[:MAX_LISTED]})


def _dangling(
    references: dict[int | None, Counter[int]],
    page_numbers: dict[int | None, int],
    contents: dict[int, set[int]],
) -> list[dict[str, int | None]]:
    return [
        {"page": page_numbers.get(xref), "mcid": mcid}
        for xref, counts in references.items()
        for mcid in sorted(counts)
        if mcid not in contents.get(page_numbers.get(xref, 0), ())
    ]


def _decoded_content(page: PageObject, budget: int) -> bytes:
    """Concatenate a page's content streams, refusing more than ``budget`` bytes.

    Returns
    -------
    bytes
        The decoded content, streams separated by a newline.

    Raises
    ------
    ToolFailedError
        The decoded content exceeds the budget.

    """
    contents = page.get("/Contents")
    contents = contents.get_object() if contents is not None else None
    streams = contents if isinstance(contents, ArrayObject) else [contents]
    parts: list[bytes] = []
    for item in streams:
        stream = item.get_object() if item is not None else None
        if isinstance(stream, StreamObject):
            data = stream.get_data()
            budget -= len(data) + bool(parts)
            parts.append(data)
            if budget < 0:
                msg = f"Page content is larger than the {MAX_CONTENT_BYTES}-byte limit"
                raise ToolFailedError(msg)
    return b"\n".join(parts)


def _property_mcids(page: PageObject) -> Callable[[str], int | None]:
    properties = pdf_dictionary(pdf_dictionary(page.get("/Resources")).get("/Properties"))

    def mcid_of(name: str) -> int | None:
        value = pdf_dictionary(properties.get(name)).get("/MCID")
        return int(value) if isinstance(value, NumberObject) else None

    return mcid_of
