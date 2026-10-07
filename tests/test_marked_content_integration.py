# SPDX-License-Identifier: MPL-2.0
"""Real veraPDF independently rejects controlled damage to a compliant Writer export."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from pypdf import PdfWriter
from pypdf.generic import ContentStream, DecodedStreamObject

from odfa11y.pdf import ExportSettings, audit_pdfua, export_pdfua, validate_pdfua

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

SEQUENCE = re.compile(rb"/[A-Za-z0-9]+\s*<<\s*/MCID\s+(\d+)\s*>>\s*BDC")


@pytest.mark.integration
@pytest.mark.parametrize("defect", ["unreferenced", "untagged"])
def test_content_errors_agree_with_verapdf_on_a_damaged_real_export(
    tmp_path: Path, external_tool: Callable[..., str], defect: str
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    verapdf = external_tool("verapdf")
    baseline = export_pdfua(
        make_minimal_odt(tmp_path / "source.odt"),
        tmp_path / "baseline.pdf",
        ExportSettings("writer_pdf_Export", soffice=soffice),
    )
    assert audit_pdfua(baseline).passed
    assert validate_pdfua(baseline, executable=verapdf).compliant
    writer = PdfWriter(clone_from=baseline)
    content = writer.pages[0].get_contents()
    assert content is not None
    data = content.get_data()
    match = SEQUENCE.search(data)
    assert match is not None, data
    replacement = (
        match[0].replace(match[1], b"100000") if defect == "unreferenced" else b"/Span BMC"
    )
    damaged = data[: match.start()] + replacement + data[match.end() :]
    stream = DecodedStreamObject()
    stream.set_data(damaged)
    writer.pages[0].replace_contents(ContentStream(stream, writer))
    path = tmp_path / "damaged.pdf"
    writer.write(path)
    report = audit_pdfua(path)
    content_rules = {f.rule_id for f in report.findings if f.rule_id.startswith("PDF02")}
    expected = {"PDF020", "PDF021"} if defect == "unreferenced" else {"PDF021", "PDF023"}
    assert content_rules == expected
    assert not report.passed
    result = validate_pdfua(path, executable=verapdf)
    assert not result.compliant
    assert {(f.clause, f.test_number) for f in result.failures} == {("7.1", "3")}
