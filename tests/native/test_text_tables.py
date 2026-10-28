# SPDX-License-Identifier: MPL-2.0
"""Writer retains valid complex table structure and exposes ambiguous intent for review."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pypdf import PdfReader

from odfa11y.families.text import MarkTableHeaders, TableHeaders
from odfa11y.pdf import audit_pdfua, validate_pdfua
from odfa11y.pipeline.native import export_document
from odfa11y.report import FactKeys
from odfa11y.source_audit import audit_odf
from odfa11y.tools import Tools
from tests.fixtures.operations import assert_refused, execute_operations
from tests.fixtures.paths import TESTS

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.mark.integration
@pytest.mark.parametrize("case", ["positive", "negative", "data-no-headers"])
def test_writer_table_classification_and_pdf_scope(
    case: str, tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    source = TESTS / "text_corpus" / f"tables-{case}.odt"
    report = audit_odf(source)
    row = report.facts[FactKeys.TEXT_TABLE_CLASSIFICATIONS][0]
    expected = {"positive": "complex-data", "negative": "ambiguous", "data-no-headers": "data"}
    assert row["classification"] == expected[case]
    findings = {finding.rule_id for finding in report.findings}
    if case == "negative":
        assert "TABLE001" in findings
        assert not any(question.kind.id == "table.headers" for question in report.decisions)
        refused = tmp_path / "refused.odt"
        assert_refused(
            execute_operations(
                source, refused, [MarkTableHeaders({"Intent": TableHeaders(rows=1)})]
            ),
            match="ambiguous.*Writer",
        )
        assert not refused.exists()
    elif case == "data-no-headers":
        assert "TABLE003" in findings
        question = next(q for q in report.decisions if q.kind.id == "table.headers")
        assert question.target is not None
        edited = tmp_path / "headers.odt"
        result = execute_operations(
            source,
            edited,
            [
                MarkTableHeaders({
                    question.target.path: TableHeaders(rows=1, fingerprint=question.fingerprint)
                })
            ],
        )
        assert result.published, result.as_dict()
        source = edited
        assert "TABLE003" not in {f.rule_id for f in audit_odf(source).findings}
    else:
        assert not {"TABLE001", "TABLE002", "TABLE003"} & findings
    output = tmp_path / "table.pdf"
    export_document(source, output, Tools(soffice=external_tool("soffice", "libreoffice")))
    assert {finding.rule_id for finding in audit_pdfua(output).findings} == (
        {"PDF008", "PDF015"} if case == "negative" else {"PDF008"}
    )
    assert validate_pdfua(output, executable=external_tool("verapdf")).compliant
    reader = PdfReader(output)
    assert "Apples" in "\n".join(page.extract_text() for page in reader.pages)
    pending = [reader.root_object["/StructTreeRoot"]]
    roles = []
    while pending:
        node = pending.pop().get_object()
        if not isinstance(node, dict):
            continue
        roles.append(str(node.get("/S", "")))
        kids = node.get("/K", [])
        pending.extend(kids if isinstance(kids, list) else [kids])
    assert "/Table" in roles
    if case != "negative":
        assert "/TH" in roles
