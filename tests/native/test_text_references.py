# SPDX-License-Identifier: MPL-2.0
"""Writer reference fixtures retain link wording and expose note reading-order review."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pypdf import PdfReader

from odfa11y.pdf import audit_pdfua, validate_pdfua
from odfa11y.pipeline.native import export_document
from odfa11y.report import FactKeys
from odfa11y.source_audit import audit_odf
from odfa11y.tools import Tools
from tests.fixtures.paths import TESTS

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.mark.integration
@pytest.mark.parametrize("case", ["positive", "negative"])
def test_writer_reference_wording_and_source_scope(
    case: str, tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    source = TESTS / "text_corpus" / f"references-{case}.odt"
    output = tmp_path / "references.pdf"
    export_document(source, output, Tools(soffice=external_tool("soffice", "libreoffice")))
    reader = PdfReader(output)
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Visit fruit" in text
    pdf_rules = {finding.rule_id for finding in audit_pdfua(output).findings}
    validation = validate_pdfua(output, executable=external_tool("verapdf"))
    if case == "positive":
        assert pdf_rules == {"PDF008", "PDF019"}
        assert not validation.compliant
        assert {(failure.clause, failure.test_number) for failure in validation.failures} == {
            ("7.18.1", "2"),
            ("7.18.5", "2"),
        }
    else:
        assert pdf_rules == {"PDF008", "PDF017"}
        assert validation.compliant
    report = audit_odf(source)
    assert report.facts[FactKeys.TEXT_REFERENCE_COUNT] == 1
    if case == "positive":
        assert "Fruit grows on trees." in text
        assert report.facts[FactKeys.TEXT_NOTE_COUNT] == 1
        assert "NOTE001" in {finding.rule_id for finding in report.findings}
        assert any(
            annotation.get_object().get("/Dest") is not None
            or annotation.get_object().get("/A", {}).get("/S") == "/GoTo"
            for page in reader.pages
            for annotation in page.get("/Annots", [])
        )
    else:
        assert "REFERENCE001" in {finding.rule_id for finding in report.findings}
