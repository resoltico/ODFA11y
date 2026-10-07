# SPDX-License-Identifier: MPL-2.0
"""Protect spreadsheet formulas, values, references, geometry and hidden content."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.content import protected_xml
from odfa11y.odf import Part, qn

from .sheets import sheet_name, sheets

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument

SHEET_TAG = "sheet\t"


def sheet_snapshot(document: OdfDocument) -> tuple[str, ...]:
    """Bind every sheet to its complete content, except name and graphic descriptions.

    Returns
    -------
    tuple[str, ...]
        Sheet-name entries followed by protected XML digests, preserving ordering,
        formulas, values, references, geometry, repeats and hidden content.

    """
    entries: list[str] = []
    for sheet in sheets(document.tree(Part.CONTENT)):
        entries.extend((
            f"{SHEET_TAG}{sheet_name(sheet)}",
            "content\t"
            + protected_xml(
                sheet,
                omitted_root_attributes=(qn("table", "name"),),
                omitted_elements=(qn("svg", "title"), qn("svg", "desc")),
            ),
        ))
    return tuple(entries)


def sheets_preserved(before: tuple[str, ...], after: tuple[str, ...], removed_blocks: int) -> bool:
    """Allow sheet names to change and nothing else to differ.

    Returns
    -------
    bool
        Whether both snapshots have the same sheets in the same order with the same protected
        content; no empty block may have been removed.

    """
    return (
        removed_blocks == 0
        and len(before) == len(after)
        and all(
            old == new or (old.startswith(SHEET_TAG) and new.startswith(SHEET_TAG))
            for old, new in zip(before, after, strict=True)
        )
    )
