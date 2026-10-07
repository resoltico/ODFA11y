# SPDX-License-Identifier: MPL-2.0
"""Read the structure of a spreadsheet: sheets, rows, cells and what each one shows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.odf import NS, qn, select_elements

if TYPE_CHECKING:
    from collections.abc import Iterator

    from lxml import etree

SHEETS = "//office:body/office:spreadsheet/table:table"
ROWS = (
    "./table:table-row | ./table:table-header-rows/table:table-row | "
    "./table:table-row-group//table:table-row | ./table:table-rows/table:table-row"
)
CELLS = "./table:table-cell | ./table:covered-table-cell"
DRAWINGS = ".//draw:*"
MIN_DATA_DIMENSION = 2
MAX_HEADER_LENGTH = 80


def sheets(tree: etree._ElementTree) -> list[etree._Element]:
    """List the sheets of a spreadsheet body in document order.

    Returns
    -------
    list[etree._Element]
        The ``table:table`` elements directly under ``office:spreadsheet``.

    """
    return select_elements(tree, SHEETS)


def sheet_name(sheet: etree._Element) -> str:
    """Read a sheet's name.

    Returns
    -------
    str
        The ``table:name``, empty when it is missing.

    """
    return sheet.get(qn("table", "name")) or ""


def cell_text(cell: etree._Element) -> str:
    """Read the text a cell shows, without the accessible text of graphics inside it.

    Returns
    -------
    str
        The cell's text with whitespace collapsed and non-breaking spaces read as spaces.

    """
    pieces = cell.xpath(
        "descendant::text()[not(ancestor::svg:title or ancestor::svg:desc "
        "or ancestor::office:binary-data)]",
        namespaces=NS,
    )
    text = "".join(piece for piece in pieces if isinstance(piece, str))
    return " ".join(text.replace("\u00a0", " ").split())


def populated_rows(sheet: etree._Element) -> Iterator[etree._Element]:
    """Yield the rows of a sheet that show any text, in order.

    Yields
    ------
    etree._Element
        Each row with at least one non-empty cell.

    """
    for row in select_elements(sheet, ROWS):
        if any(cell_text(cell) for cell in select_elements(row, CELLS)):
            yield row


def is_empty(sheet: etree._Element) -> bool:
    """Whether a sheet shows no text and holds no graphic, chart or shape.

    Returns
    -------
    bool
        True when nothing in the sheet could be read, seen or navigated to.

    """
    return next(populated_rows(sheet), None) is None and not select_elements(sheet, DRAWINGS)


def is_data_sheet(sheet: etree._Element) -> bool:
    """Whether a sheet looks like a table of data: a short labelled first row and more rows.

    The test is deliberately conservative; a sheet of long prose or a single filled row is
    not data-like.

    Returns
    -------
    bool
        True when the first populated row has at least two short labels and another
        populated row follows.

    """
    rows = populated_rows(sheet)
    first = next(rows, None)
    if first is None or next(rows, None) is None:
        return False
    labels = [text for cell in select_elements(first, CELLS) if (text := cell_text(cell))]
    return len(labels) >= MIN_DATA_DIMENSION and all(
        len(label) <= MAX_HEADER_LENGTH for label in labels
    )


def sheet_index(element: etree._Element) -> int:
    """Count the sheets before the one holding an element.

    Returns
    -------
    int
        The zero-based position of the element's sheet; zero when it has no sheet.

    """
    owner = element.xpath("ancestor-or-self::table:table[1]", namespaces=NS)
    if not isinstance(owner, list) or not owner:
        return 0
    preceding = owner[0].xpath("count(preceding-sibling::table:table)", namespaces=NS)
    return int(preceding) if isinstance(preceding, float) else 0
