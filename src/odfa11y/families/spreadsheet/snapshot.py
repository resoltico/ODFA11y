# SPDX-License-Identifier: MPL-2.0
"""What a spreadsheet shows, for the executor to compare before and after an edit.

The snapshot lists every sheet name and, for each sheet, the text of every non-empty cell
with its row and column. A rename-only edit may change sheet names (the sheets keep their
order and count) and nothing else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.odf import Part, qn, select_elements

from .sheets import CELLS, ROWS, cell_text, sheet_name, sheets

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument

SHEET_TAG = "sheet\t"
CELL_TAG = "cell\t"


def sheet_snapshot(document: OdfDocument) -> tuple[str, ...]:
    """List the sheet names and non-empty cell texts of a spreadsheet.

    Returns
    -------
    tuple[str, ...]
        A ``sheet`` entry per sheet, each followed by a ``cell`` entry (position and text)
        for every non-empty cell, in document order.

    """
    entries: list[str] = []
    for sheet in sheets(document.tree(Part.CONTENT)):
        entries.append(f"{SHEET_TAG}{sheet_name(sheet)}")
        entries.extend(_cell_entries(sheet))
    return tuple(entries)


def sheets_preserved(before: tuple[str, ...], after: tuple[str, ...], removed_blocks: int) -> bool:
    """Allow sheet names to change and nothing else to differ.

    Returns
    -------
    bool
        Whether both snapshots have the same sheets in the same order with the same cell
        texts at the same positions; no empty block may have been removed.

    """
    return (
        removed_blocks == 0
        and len(before) == len(after)
        and all(
            old == new or (old.startswith(SHEET_TAG) and new.startswith(SHEET_TAG))
            for old, new in zip(before, after, strict=True)
        )
    )


def _cell_entries(sheet: etree._Element) -> list[str]:
    entries: list[str] = []
    row_number = 1
    for row in select_elements(sheet, ROWS):
        column_number = 1
        for cell in select_elements(row, CELLS):
            text = cell_text(cell)
            if text:
                entries.append(f"{CELL_TAG}{row_number},{column_number}\t{text}")
            column_number += _repeat(cell, "number-columns-repeated")
        row_number += _repeat(row, "number-rows-repeated")
    return entries


def _repeat(element: etree._Element, attribute: str) -> int:
    try:
        return max(int(element.get(qn("table", attribute), "1")), 1)
    except ValueError:
        return 1
