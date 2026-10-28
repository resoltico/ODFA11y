# SPDX-License-Identifier: MPL-2.0
"""Nested table identity retains protected contents across legal header representations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odfa11y.content import table_content_fingerprint, table_fingerprint
from odfa11y.families.text import MarkTableHeaders, TableHeaders
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate

from .documents import Variant, make_flat
from .operation_execution import execute_operations

if TYPE_CHECKING:
    from pathlib import Path

BODY = (
    '<office:text><table:table table:name="Outer"><table:table-column/>'
    "<table:table-row><table:table-cell><text:p>Outer header</text:p>"
    '<table:table table:name="Inner"><table:table-column table:number-columns-repeated="3"/>'
    '<table:table-row table:number-rows-repeated="3"><table:table-cell>'
    '<text:p><text:a xlink:type="simple" xlink:href="https://example.test/">'
    "Inner value</text:a></text:p>"
    "</table:table-cell></table:table-row></table:table>"
    "</table:table-cell></table:table-row></table:table></office:text>"
)


@pytest.mark.parametrize("count", ["3", "+3", "03"])
def test_nested_headers_and_repeat_splits_preserve_full_reviewed_outer_identity(
    tmp_path: Path,
    count: str,
) -> None:
    source = make_flat(
        tmp_path, "text", Variant(body=BODY.replace('repeated="3"', f'repeated="{count}"'))
    )
    document = OdfDocument.open(source)
    outer, inner = select_elements(document.tree(Part.CONTENT), "//table:table")
    reviewed = table_fingerprint(outer, document)
    snapshot = table_content_fingerprint(outer, document)
    operation = MarkTableHeaders({
        "Outer": TableHeaders(columns=1, fingerprint=reviewed),
        "Inner": TableHeaders(rows=1, columns=1, fingerprint=table_fingerprint(inner, document)),
    })
    output = tmp_path / "reviewed.fodt"
    result = execute_operations(source, output, [operation])
    assert result.changed
    edited = OdfDocument.open(output)
    outer = select_elements(edited.tree(Part.CONTENT), "//table:table")[0]
    assert table_fingerprint(outer, edited) == reviewed
    assert table_content_fingerprint(outer, edited) == snapshot
    assert validate(edited).count == 0
    assert not execute_operations(output, tmp_path / "again.fodt", [operation]).changed
    link = select_elements(outer, ".//text:a")[0]
    link.set(qn("xlink", "href"), "https://changed.example/")
    assert table_fingerprint(outer, edited) != reviewed
