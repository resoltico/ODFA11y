# SPDX-License-Identifier: MPL-2.0
"""Build synthetic spreadsheets, as packages or flat XML, with selected structural features."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .documents import Variant, make_flat, make_package

if TYPE_CHECKING:
    from pathlib import Path

LAYOUTS = {"package": make_package, "flat": make_flat}
HIDDEN_SHEET_STYLE = (
    '<style:style style:name="taHidden" style:family="table">'
    '<style:table-properties table:display="false"/></style:style>'
)


def text_cell(text: str, attributes: str = "") -> str:
    """Write a cell showing text.

    Returns
    -------
    str
        A ``table:table-cell`` element.

    """
    return (
        f'<table:table-cell office:value-type="string" {attributes}>'
        f"<text:p>{text}</text:p></table:table-cell>"
    )


def row(*cells: str, attributes: str = "") -> str:
    """Write a table row.

    Returns
    -------
    str
        A ``table:table-row`` element.

    """
    return f"<table:table-row {attributes}>{''.join(cells)}</table:table-row>"


def sheet(name: str, *rows: str, style: str = "", header_rows: int = 0) -> str:
    """Write a sheet; the first ``header_rows`` rows are marked as header rows.

    Returns
    -------
    str
        A ``table:table`` element with two columns.

    """
    marked = "".join(rows[:header_rows])
    body = f"<table:table-header-rows>{marked}</table:table-header-rows>" if header_rows else ""
    style_attribute = f' table:style-name="{style}"' if style else ""
    return (
        f'<table:table table:name="{name}"{style_attribute}>'
        f"<table:table-column/><table:table-column/>{body}{''.join(rows[header_rows:])}"
        "</table:table>"
    )


def data_sheet(name: str, *, header_rows: int = 0, merged: bool = False) -> str:
    """Write a sheet that looks like a table of data.

    Returns
    -------
    str
        A header row of labels followed by two data rows, one merged when asked.

    """
    last = (
        row(text_cell("Total", 'table:number-columns-spanned="2"'), "<table:covered-table-cell/>")
        if merged
        else row(text_cell("Pears"), text_cell("4"))
    )
    return sheet(
        name,
        row(text_cell("Item"), text_cell("Amount")),
        row(text_cell("Apples"), text_cell("3")),
        last,
        header_rows=header_rows,
    )


def picture(
    name: str = "Logo", href: str = "Pictures/logo.png", alt: str = "", data: str = ""
) -> str:
    """Write a picture frame inside a cell.

    Returns
    -------
    str
        A cell holding a ``draw:frame``; ``alt`` is the frame's ``svg:title`` and
        ``svg:desc`` children, ready-made, and ``data`` embeds base64 image data in a flat
        document instead of pointing at a package member.

    """
    image = (
        f"<draw:image><office:binary-data>{data}</office:binary-data></draw:image>"
        if data
        else f'<draw:image xlink:href="{href}" xlink:type="simple"/>'
    )
    return (
        "<table:table-cell><text:p/>"
        f'<draw:frame draw:name="{name}" svg:width="1cm" svg:height="1cm">{image}{alt}'
        "</draw:frame></table:table-cell>"
    )


def make_spreadsheet(
    directory: Path,
    layout: str,
    *sheets: str,
    automatic_styles: str = "",
    kind: str = "spreadsheet",
) -> Path:
    """Write a spreadsheet holding the given sheets.

    Returns
    -------
    Path
        The package or flat document.

    """
    body = f"<office:spreadsheet>{''.join(sheets)}</office:spreadsheet>"
    variant = Variant(body=body, automatic_styles=automatic_styles)
    return LAYOUTS[layout](directory, kind, variant)
