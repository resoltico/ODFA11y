# SPDX-License-Identifier: MPL-2.0
"""Fingerprint the object a reviewed plan entry refers to, to detect document drift.

A fingerprint covers identity and facts that no operation changes, so applying a plan
again to its own output reproduces the same fingerprint.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.odf import NS, qn, select_elements

from .text import element_text

if TYPE_CHECKING:
    from collections.abc import Sequence

    from lxml import etree

FINGERPRINT_LENGTH = 12
COLUMN_SELECTOR = (
    "./table:table-column | ./table:table-columns/table:table-column | "
    "./table:table-header-columns/table:table-column"
)
ROW_SELECTOR = (
    "./table:table-row | ./table:table-header-rows/table:table-row | "
    "./table:table-row-group//table:table-row | ./table:table-rows/table:table-row"
)


def graphics_fingerprint(frames: Sequence[etree._Element]) -> str:
    """Fingerprint the graphic frames a selector addresses.

    Returns
    -------
    str
        A short hexadecimal digest of each frame's name, image file, size and anchor.

    """
    return _digest([_frame_facts(frame) for frame in frames])


def table_fingerprint(table: etree._Element) -> str:
    """Fingerprint a table by name, shape and the text of its first row.

    Returns
    -------
    str
        A short hexadecimal digest that header marking does not change.

    """
    rows = select_elements(table, ROW_SELECTOR)
    columns = sum(
        int(column.get(qn("table", "number-columns-repeated"), "1"))
        for column in select_elements(
            table,
            COLUMN_SELECTOR,
        )
    )
    first = (
        [
            element_text(cell)
            for cell in select_elements(rows[0], "./table:table-cell | ./table:covered-table-cell")
        ]
        if rows
        else []
    )
    return _digest([table.get(qn("table", "name")), columns, len(rows), first])


def _frame_facts(frame: etree._Element) -> list[str | None]:
    image = frame.find("draw:image", NS)
    href = image.get(qn("xlink", "href")) if image is not None else None
    return [
        frame.get(qn("draw", "name")),
        Path(href).name if href else None,
        frame.get(qn("svg", "width")),
        frame.get(qn("svg", "height")),
        frame.get(qn("text", "anchor-type")),
    ]


def _digest(facts: object) -> str:
    payload = json.dumps(facts, ensure_ascii=True, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:FINGERPRINT_LENGTH]
