# SPDX-License-Identifier: MPL-2.0
"""Writer reference fixtures retain link wording and expose note reading-order review."""

lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest
from pypdf import PdfReader

from odfa11y.application.export import export_document
from odfa11y.application.tools import Tools
from odfa11y.audit import audit_odf
from odfa11y.families.text.references.audit import ReferenceMeasurements
from odfa11y.pdf import audit_pdfua
from odfa11y.rules import registry as rules
from tests.fixtures.measurements import measured, measurement
from tests.fixtures.native import validate_pdfua
from tests.fixtures.paths import TESTS


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
        assert pdf_rules == {rules.PDF009.id, rules.PDF020.id}
        assert not validation.compliant
        assert {(failure.clause, failure.test_number) for failure in validation.failures} == {
            ("7.18.1", "2"),
            ("7.18.5", "2"),
        }
    else:
        assert pdf_rules == {rules.PDF009.id, rules.PDF018.id}
        assert validation.compliant
    report = audit_odf(source)
    assert measured(measurement(report, ReferenceMeasurements).reference_count) == 1
    if case == "positive":
        assert "Fruit grows on trees." in text
        assert measured(measurement(report, ReferenceMeasurements).note_count) == 1
        assert rules.NOTE001.id in {finding.rule_id for finding in report.findings}
        assert any(
            annotation.get_object().get("/Dest") is not None
            or annotation.get_object().get("/A", {}).get("/S") == "/GoTo"
            for page in reader.pages
            for annotation in page.get("/Annots", [])
        )
    else:
        assert rules.REF001.id in {finding.rule_id for finding in report.findings}
