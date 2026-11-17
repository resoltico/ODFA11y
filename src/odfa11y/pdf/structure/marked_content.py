# SPDX-License-Identifier: AGPL-3.0-only
"""Reconcile the marked content of each page with the structure tree that should own it."""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Annotated, Literal
lazy from collections.abc import Iterable

from odfa11y.contracts import Description
from odfa11y.pdf.reading.reader import PageContent
from odfa11y.pdf.structure.graphics import described_graphics
from odfa11y.rules import registry as rules
from odfa11y.rules.details import DETAIL_ITEMS
lazy from odfa11y.pdf.reading.structure import StructureNode
lazy from odfa11y.report import Report


@dataclass(frozen=True, slots=True)
class MarkedContentMeasurements:
    """Measurements produced by pdf-marked-content analysis; None denotes unmeasured data."""

    producer: Literal["pdf-marked-content"] = field(default="pdf-marked-content", init=False)
    marked_content_id_count: Annotated[int | None, Description("Marked content identifiers.")] = (
        None
    )


def check_marked_content(
    pages: Iterable[PageContent], nodes: list[StructureNode], report: Report
) -> int:
    """Report page content that is not tagged, and structure references that match no content.

    The reader supplies page and independent Form scopes from its single bounded walk.
    This check reconciles unowned MCIDs, missing or multiply owned content references,
    and text outside tagged content and artifacts. veraPDF remains the validator.

    Returns
    -------
    int
        Described Figures containing graphical operations reconciled on actual pages.

    """
    references: dict[tuple[int | None, int | None], Counter[int]] = defaultdict(Counter)
    for node in nodes:
        for reference in node.marked_content:
            references[reference.identity][reference.mcid] += 1
    untagged: list[dict[str, int]] = []
    unreferenced: list[dict[str, object]] = []
    page_numbers: dict[tuple[int | None, int | None], int] = {}
    contents: dict[tuple[int | None, int | None], set[int]] = {}
    painted: dict[tuple[int | None, int | None], set[int]] = {}
    for number, content in enumerate(pages, start=1):
        page = content.page
        xref = page.indirect_reference.idnum if page.indirect_reference else None
        for stream, scan in content.scopes:
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
                    "mcids": loose[:DETAIL_ITEMS],
                })
            if scan.unmarked_text_operations:
                untagged.append({
                    "page": number,
                    "text_operations": scan.unmarked_text_operations,
                    **stream_details,
                })
    report.measure(
        MarkedContentMeasurements(
            marked_content_id_count=sum(len(ids) for ids in contents.values())
        )
    )
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
        report.raise_(
            rules.PDF023, details={"count": len(duplicated), "mcids": duplicated[:DETAIL_ITEMS]}
        )
    return described_graphics(nodes, painted)


def _report(
    report: Report,
    unreferenced: list[dict[str, object]],
    untagged: list[dict[str, int]],
    dangling: list[dict[str, int | None]],
) -> None:
    if unreferenced:
        report.raise_(rules.PDF021, details={"pages": unreferenced[:DETAIL_ITEMS]})
    if dangling:
        report.raise_(
            rules.PDF022, details={"count": len(dangling), "references": dangling[:DETAIL_ITEMS]}
        )
    if untagged:
        report.raise_(rules.PDF024, details={"pages": untagged[:DETAIL_ITEMS]})


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
