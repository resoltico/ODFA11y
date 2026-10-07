# SPDX-License-Identifier: MPL-2.0
"""Prove local cached chart-range boundaries without materializing repeated table data."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from odfa11y.content import axis_count, cell_at, declarations, repeated
from odfa11y.errors import RemediationError
from odfa11y.odf import qn, select_elements

if TYPE_CHECKING:
    from collections.abc import Iterator

    from lxml import etree

TABLE_NAME = r"(?:'(?:[^']|'')+'|[^.\s:]+)"
RANGE = re.compile(
    rf"(?P<table>\$?{TABLE_NAME})?\.\$?(?P<column>[A-Za-z]+)\$?(?P<row>[0-9]+)"
    rf"(?::(?P<endtable>\$?{TABLE_NAME})?\.\$?(?P<endcolumn>[A-Za-z]+)\$?(?P<endrow>[0-9]+))?"
)


@dataclass(frozen=True, slots=True)
class LocalRange:
    """Resolved local cache bounds, retaining compressed table declarations."""

    table: etree._Element
    first_row: int
    last_row: int
    first_column: int
    last_column: int

    @property
    def shape(self) -> tuple[int, int]:
        """The logical row and column dimensions."""
        return self.last_row - self.first_row + 1, self.last_column - self.first_column + 1

    def cells(self) -> Iterator[etree._Element]:
        """Visit each intersecting physical cell once, without expanding repeats.

        Yields
        ------
        etree._Element
            Cached cells whose logical runs intersect these bounds.

        """
        row_position = 1
        for row in declarations(self.table, "rows"):
            next_row = row_position + repeated(row, "number-rows-repeated")
            if row_position > self.last_row:
                break
            if next_row > self.first_row:
                yield from self._row_cells(row)
            row_position = next_row

    def _row_cells(self, row: etree._Element) -> Iterator[etree._Element]:
        column_position = 1
        for cell in select_elements(row, "./table:table-cell | ./table:covered-table-cell"):
            next_column = column_position + repeated(cell, "number-columns-repeated")
            if column_position > self.last_column:
                break
            if next_column > self.first_column:
                yield cell
            column_position = next_column


def range_shape(chart: etree._Element, address: str) -> tuple[int, int] | None:
    """Inspect a range without expanding cached cells.

    A reversed or out-of-bounds local range propagates ``RemediationError``.

    Returns
    -------
    tuple[int, int] | None
        Logical dimensions, or None for unsupported syntax/nonlocal data.

    """
    resolved = resolve_range(chart, address)
    return resolved.shape if resolved is not None else None


def resolve_range(chart: etree._Element, address: str) -> LocalRange | None:
    """Resolve a standard local range and validate its declared boundaries.

    Returns
    -------
    LocalRange | None
        Compressed local range, or None for unsupported syntax/nonlocal data.

    Raises
    ------
    RemediationError
        A resolved local range is reversed or exceeds its declared grid.

    """
    match = RANGE.fullmatch(address)
    if match is None:
        return None
    tables = select_elements(chart, "./table:table")
    name = _table_name(match["table"])
    if name is None and len(tables) == 1:
        name = tables[0].get(qn("table", "name"))
    matches = [table for table in tables if table.get(qn("table", "name")) == name]
    if len(matches) != 1 or _table_name(match["endtable"]) not in {None, name}:
        return None
    table = matches[0]
    rows, columns = axis_count(table, "rows"), axis_count(table, "columns")
    try:
        first_row = int(match["row"].lstrip("0") or "0")
        last_row = int((match["endrow"] or match["row"]).lstrip("0") or "0")
    except ValueError:
        return None
    first_column = _column(match["column"], columns)
    last_column = _column(match["endcolumn"] or match["column"], columns)
    if not (1 <= first_row <= last_row <= rows and 1 <= first_column <= last_column <= columns):
        msg = "A local chart data range is reversed or exceeds its declared table."
        raise RemediationError(msg)
    if (
        cell_at(table, first_row, first_column) is None
        or cell_at(table, last_row, last_column) is None
    ):
        return None  # The boundary is declared, but its cache contains no inspectable cells.
    return LocalRange(table, first_row, last_row, first_column, last_column)


def _table_name(name: str | None) -> str | None:
    if name is None:
        return None
    return name.removeprefix("$").removeprefix("'").removesuffix("'").replace("''", "'")


def _column(letters: str, limit: int) -> int:
    number = 0
    for letter in letters.upper():
        number = number * 26 + ord(letter) - ord("A") + 1
        if number > limit:
            break
    return number
