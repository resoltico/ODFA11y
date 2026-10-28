# SPDX-License-Identifier: MPL-2.0
"""Writer visibility fixtures preserve revision history and disclose actual exported content."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree
from pypdf import PdfReader

from odfa11y.odf import OdfDocument, Part
from odfa11y.pipeline.native import export_document
from odfa11y.remediation import SetMetadata
from odfa11y.report import FactKeys
from odfa11y.source_audit import audit_odf
from odfa11y.tools import Tools
from tests.fixtures.operations import execute_operations
from tests.fixtures.paths import TESTS

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.mark.integration
@pytest.mark.parametrize("case", ["positive", "negative"])
def test_writer_revision_visibility_and_reading_order_scope(
    case: str, tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    source = TESTS / "text_corpus" / f"visibility-{case}.odt"
    report = audit_odf(source)
    findings = {finding.rule_id for finding in report.findings}
    assert not {"REVISION002", "REVISION003", "HIDDEN002"} & findings
    assert ("REVISION001" in findings) is (case == "negative")
    assert ("HIDDEN001" in findings) is (case == "negative")
    assert ("ORDER001" in findings) is (case == "negative")
    facts = report.facts[FactKeys.TEXT_REVISION_RELATIONSHIPS]
    assert facts["declarations"] == facts["markers"] == (1 if case == "negative" else 0)
    edited = tmp_path / "reviewed.odt"
    before = etree.tostring(OdfDocument.open(source).tree(Part.CONTENT))
    result = execute_operations(source, edited, [SetMetadata(title="Reviewed visibility")])
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
