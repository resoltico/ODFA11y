# SPDX-License-Identifier: MPL-2.0
"""Reconcile the marked content of each page with the structure tree that should own it."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import TYPE_CHECKING

from pypdf.generic import ArrayObject, StreamObject

from odfa11y.errors import ToolFailedError
from odfa11y.pdf_limits import MAX_CONTENT_BYTES
from odfa11y.report import rules

from .form_content import FormScanner
from .graphic_presence import described_graphics
from .link_structure import MAX_LISTED
from .structure_walk import pdf_dictionary

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pypdf import PageObject

    from odfa11y.report import Report

    from .structure_walk import StructureNode


def check_marked_content(
    pages: Iterable[PageObject], nodes: list[StructureNode], report: Report
) -> int:
    """Report page content that is not tagged, and structure references that match no content.

    Each page's content stream is scanned for marked-content sequences. Findings: MCIDs no
    structure element refers to (``PDF020``), references to MCIDs the page does not contain
    (``PDF021``), MCIDs referred to more than once (``PDF022``) and text shown outside tagged
    content and ``/Artifact`` (``PDF023``). Invoked Forms and their ``/Stm`` references
    are inspected in independent stream scopes. The check claims only these correspondences;
    veraPDF remains the validator. Decoded content beyond ``MAX_CONTENT_BYTES`` in all pages
    raises ``ToolFailedError``.

    Returns
    -------
    int
        Described Figures containing graphical operations reconciled on actual pages.

    """
    references: dict[tuple[int | None, int | None], Counter[int]] = defaultdict(Counter)
    for node in nodes:
        for reference in node.marked_content:
            references[reference.identity][reference.mcid] += 1
    budget = MAX_CONTENT_BYTES
    untagged: list[dict[str, int]] = []
    unreferenced: list[dict[str, object]] = []
    page_numbers: dict[tuple[int | None, int | None], int] = {}
    contents: dict[tuple[int | None, int | None], set[int]] = {}
    painted: dict[tuple[int | None, int | None], set[int]] = {}
    for number, page in enumerate(pages, start=1):
        data = _decoded_content(page, budget)
        budget -= len(data)
        scanner = FormScanner()
        scan = scanner.scan(data, pdf_dictionary(page.get("/Resources")))
        scanner.streams[None] = scan
        xref = page.indirect_reference.idnum if page.indirect_reference else None
        for stream, scan in scanner.streams.items():
            identity = (xref if stream is None else None, stream)
            page_numbers[identity] = number
            contents.setdefault(identity, set()).update(scan.mcids)
            painted.setdefault(identity, set()).update(scan.graphical_mcids)
            stream_details = {"stream": stream} if stream is not None else {}
            loose = sorted(scan.mcids - set(references.get(identity, ())))
            if loose:
                unreferenced.append({
                    "page": number,
                    "count": len(loose),
                    "mcids": loose[:MAX_LISTED],
                })
            if scan.unmarked_text_operations:
                untagged.append({
                    "page": number,
                    "text_operations": scan.unmarked_text_operations,
                    **stream_details,
                })
    report.metadata["marked_content_ids"] = sum(len(ids) for ids in contents.values())
    _report(report, unreferenced, untagged, _dangling(references, page_numbers, contents))
    duplicated = [
        {
            "page": page_numbers.get(xref),
            "mcid": mcid,
            "references": count,
            **({"stream": xref[1]} if xref[1] is not None else {}),
        }
        for xref, counts in references.items()
        for mcid, count in counts.items()
        if count > 1
    ]
    if duplicated:
        report.add(
            rules.PDF022, details={"count": len(duplicated), "mcids": duplicated[:MAX_LISTED]}
        )
    return described_graphics(nodes, painted)


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
    references: dict[tuple[int | None, int | None], Counter[int]],
    page_numbers: dict[tuple[int | None, int | None], int],
    contents: dict[tuple[int | None, int | None], set[int]],
) -> list[dict[str, int | None]]:
    return [
        {
            "page": page_numbers.get(xref),
            "mcid": mcid,
            **({"stream": xref[1]} if xref[1] is not None else {}),
        }
        for xref, counts in references.items()
        for mcid in sorted(counts)
        if mcid not in contents.get(xref, ())
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
