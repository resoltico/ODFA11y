# SPDX-License-Identifier: MPL-2.0
"""Resolve semantic header intervals, including valid grouped/nonleading bands."""

from __future__ import annotations

import operator
from bisect import bisect_right
from dataclasses import dataclass
from typing import TYPE_CHECKING

from odfa11y.content import AXES, declarations, repeated
from odfa11y.odf import qn, select_elements

if TYPE_CHECKING:
    from lxml import etree


@dataclass(frozen=True)
class HeaderBands:
    """Half-open logical header intervals, coalesced independently of physical repeats."""

    intervals: tuple[tuple[int, int], ...]

    @property
    def count(self) -> int:
        """Count semantic header declarations without expanding repeated axes."""
        return sum(end - start for start, end in self.intervals)

    @property
    def leading(self) -> bool:
        """Whether this axis can be represented by the leading-band decision API."""
        return not self.intervals or (len(self.intervals) == 1 and self.intervals[0][0] == 0)

    def crosses(self, position: int, span: int) -> bool:
        """Check whether a span crosses a header/data relationship boundary.

        Returns
        -------
        bool
            True when the span includes both header and data positions.

        """
        index = bisect_right(self.intervals, position, key=operator.itemgetter(0))
        if index and position < self.intervals[index - 1][1]:
            boundary = self.intervals[index - 1][1]
        elif index < len(self.intervals):
            boundary = self.intervals[index][0]
        else:
            return False
        return boundary < position + span


def header_bands(table: etree._Element, axis: str) -> HeaderBands:
    """Read header membership from the target table, excluding nested tables.

    Returns
    -------
    HeaderBands
        Exact logical header intervals, including grouped headers.

    """
    header = qn("table", AXES[axis][1])
    position = 0
    intervals: list[tuple[int, int]] = []
    for node in declarations(table, axis):
        count = repeated(node, AXES[axis][2])
        marked = any(
            parent.tag == header
            for parent in node.iterancestors()
            if next(parent.iterancestors(qn("table", "table")), None) is table
        )
        if marked:
            if intervals and intervals[-1][1] == position:
                intervals[-1] = (intervals[-1][0], position + count)
            else:
                intervals.append((position, position + count))
        position += count
    return HeaderBands(tuple(intervals))


def relationships_cross_headers(
    table: etree._Element, rows: HeaderBands, columns: HeaderBands
) -> bool:
    """Check every actual span against semantic header/data intervals.

    The caller establishes the bounded complex grid before invoking this expansion.

    Returns
    -------
    bool
        Whether at least one merged origin crosses an actual semantic band boundary.

    """
    row_position = 0
    for row in declarations(table, "rows"):
        for _ in range(repeated(row, "number-rows-repeated")):
            column = 0
            for cell in select_elements(row, "./table:table-cell | ./table:covered-table-cell"):
                for _ in range(repeated(cell, "number-columns-repeated")):
                    if cell.tag == qn("table", "table-cell") and (
                        rows.crosses(row_position, repeated(cell, "number-rows-spanned"))
                        or columns.crosses(column, repeated(cell, "number-columns-spanned"))
                    ):
                        return True
                    column += 1
            row_position += 1
    return False
