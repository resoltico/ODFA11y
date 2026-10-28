# SPDX-License-Identifier: MPL-2.0
"""Check declared grid occupancy independently of semantic table intent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from odfa11y.content import axis_count, declarations, repeated
from odfa11y.errors import RemediationError
from odfa11y.odf import qn, select_elements

if TYPE_CHECKING:
    from lxml import etree

MAX_COMPLEX_CELLS = 100_000
CELL = qn("table", "table-cell")
COVERED = qn("table", "covered-table-cell")


@dataclass(frozen=True)
class Grid:
    """Validated dimensions and whether actual span/coverage relationships exist."""

    rows: int
    columns: int
    complex: bool


def inspect_grid(table: etree._Element) -> Grid:
    """Validate rectangular rows and complete nonoverlapping merged-cell coverage.

    Returns
    -------
    Grid
        Logical dimensions, without expanding simple repeated grids.

    Raises
    ------
    RemediationError
        The grid is inconsistent or a complex expansion exceeds the inspection bound.

    """
    rows = declarations(table, "rows")
    height, width = axis_count(table, "rows"), axis_count(table, "columns")
    complex_grid = False
    for row in rows:
        cells = select_elements(row, "./table:table-cell | ./table:covered-table-cell")
        row_width = sum(repeated(cell, "number-columns-repeated") for cell in cells)
        if row_width != width:
            message = "Table row width differs from the declared column grid."
            raise RemediationError(message)
        for cell in cells:
            complex_grid |= (
                cell.tag == COVERED
                or repeated(cell, "number-columns-spanned") > 1
                or repeated(cell, "number-rows-spanned") > 1
            )
    grid = Grid(height, width, complex_grid)
    if complex_grid:
        if height * width > MAX_COMPLEX_CELLS:
            message = "Complex grid exceeds bounded inspection; review the table in Writer."
            raise RemediationError(message)
        _inspect_coverage(rows, grid)
    return grid


def _inspect_coverage(rows: list[etree._Element], grid: Grid) -> None:
    occupied: set[tuple[int, int]] = set()
    row_position = 0
    for row in rows:
        for _ in range(repeated(row, "number-rows-repeated")):
            column = 0
            for cell in select_elements(row, "./table:table-cell | ./table:covered-table-cell"):
                for _ in range(repeated(cell, "number-columns-repeated")):
                    _occupy(cell, row_position, column, grid, occupied)
                    column += 1
            row_position += 1


def _occupy(
    cell: etree._Element, row: int, column: int, grid: Grid, occupied: set[tuple[int, int]]
) -> None:
    if cell.tag == COVERED:
        if (row, column) not in occupied:
            message = "Covered cell has no spanning origin."
            raise RemediationError(message)
        return
    height = repeated(cell, "number-rows-spanned")
    width = repeated(cell, "number-columns-spanned")
    if row + height > grid.rows or column + width > grid.columns:
        message = "Spanning cell extends beyond the declared grid."
        raise RemediationError(message)
    for y in range(row, row + height):
        for x in range(column, column + width):
            if (y, x) in occupied:
                message = "Spanning origins overlap or a covered placeholder is missing."
                raise RemediationError(message)
            occupied.add((y, x))
