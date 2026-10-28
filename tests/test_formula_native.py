# SPDX-License-Identifier: MPL-2.0
"""Invented local Calc formulas retain source bytes and real exported results."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pypdf import PdfReader

from odfa11y.native.export_context import native_export_limitations
from odfa11y.odf import OdfDocument
from odfa11y.pipeline.native import export_document
from odfa11y.tools import Tools

from .documents import Variant, make_flat

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.mark.integration
@pytest.mark.parametrize("prefix", ["of:", "formula:", ""])
def test_real_calc_accepts_local_nested_formulas_without_mutating_source(
    tmp_path: Path, external_tool: Callable[..., str], prefix: str
) -> None:
    # Source invented here; runtime/tool identity is recorded by the native test job's doctor.
    body = (
        '<office:spreadsheet xmlns:of="urn:oasis:names:tc:opendocument:xmlns:of:1.2" '
        'xmlns:formula="urn:oasis:names:tc:opendocument:xmlns:of:1.2">'
        '<table:table table:name="Totals"><table:table-column/>'
        '<table:table-row><table:table-cell office:value-type="float" office:value="20">'
        "<text:p>20</text:p></table:table-cell></table:table-row>"
        '<table:table-row><table:table-cell office:value-type="float" office:value="22">'
        "<text:p>22</text:p></table:table-cell></table:table-row>"
        f'<table:table-row><table:table-cell table:formula="{prefix}=SUM([.A1:.A2])+ABS(0)" '
        'office:value-type="float" office:value="42"><text:p>42</text:p>'
        "</table:table-cell></table:table-row></table:table></office:spreadsheet>"
    )
    source = make_flat(tmp_path, "spreadsheet", Variant(body=body))
    original = source.read_bytes()
    assert native_export_limitations(OdfDocument.open(source))["rendering_dependencies"] == 0
    pdf = export_document(
        source,
        tmp_path / "formula.pdf",
        Tools(soffice=external_tool("soffice", "libreoffice")),
    )
    assert "42" in " ".join(page.extract_text() for page in PdfReader(pdf).pages)
    assert source.read_bytes() == original
