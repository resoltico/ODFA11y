# SPDX-License-Identifier: MPL-2.0
"""Writer visibility fixtures preserve revision history and disclose actual exported content."""

lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest
from lxml import etree
from pypdf import PdfReader

from odfa11y.application.export import export_document
from odfa11y.application.tools import Tools
from odfa11y.audit import audit_odf
from odfa11y.families.text.visibility.revisions import RevisionMeasurements
from odfa11y.odf import OdfDocument, Part
from odfa11y.rules import registry as rules
from tests.fixtures.answers import metadata_input
from tests.fixtures.measurements import measured, measurement
from tests.fixtures.operations import apply_answers
from tests.fixtures.paths import TESTS


@pytest.mark.parametrize("case", ["positive", "negative"])
def test_writer_revision_visibility_and_reading_order_scope(
    case: str, tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    source = TESTS / "corpus/structure" / f"visibility-{case}.odt"
    report = audit_odf(source)
    findings = {finding.rule_id for finding in report.findings}
    assert (
        not {
            rules.REVISION001.id,
            rules.REVISION004.id,
            rules.ORDER001.id,
        }
        & findings
    )
    assert (rules.REVISION006.id in findings) is (case == "negative")
    assert (rules.ORDER003.id in findings) is (case == "negative")
    assert (rules.ORDER002.id in findings) is (case == "negative")
    facts = measured(measurement(report, RevisionMeasurements).revision_relationships)
    assert facts["declarations"] == facts["markers"] == (1 if case == "negative" else 0)
    edited = tmp_path / "reviewed.odt"
    before = etree.tostring(OdfDocument.open(source).tree(Part.CONTENT))
    result = apply_answers(source, edited, [metadata_input(title="Reviewed visibility")])
    assert result.published, result.as_dict()
    assert etree.tostring(OdfDocument.open(edited).tree(Part.CONTENT)) == before
    output = tmp_path / "visibility.pdf"
    export_document(edited, output, Tools(soffice=external_tool("soffice", "libreoffice")))
    text = "\n".join(page.extract_text() for page in PdfReader(output).pages)
    assert "Visible words." in text
    assert "Hidden words." not in text
    if case == "negative":
        # This exporter view includes tracked deletions: inspection must retain human review.
        assert "Deleted words." in text
        assert "Column words." in text
        assert "Floating words." in text
