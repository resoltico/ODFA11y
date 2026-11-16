# SPDX-License-Identifier: MPL-2.0
"""Writer retains valid complex table structure and exposes ambiguous intent for review."""

lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest
from pypdf import PdfReader

from odfa11y.application.tools import Tools
from odfa11y.audit import audit_odf
from odfa11y.audit.validation import validate_pdfua
from odfa11y.families.text.tables.audit import MeasuredTable, TableMeasurements
from odfa11y.pdf import audit_pdfua
from odfa11y.rules import registry as rules
from odfa11y.run.native import export_document
from odfa11y.targets import require_target
from tests.fixtures.answers import header_answer, header_inputs
from tests.fixtures.measurements import measured, measurement
from tests.fixtures.operations import apply_answers, assert_refused
from tests.fixtures.paths import TESTS


@pytest.mark.parametrize("case", ["positive", "negative", "data-no-headers"])
def test_writer_table_classification_and_pdf_scope(
    case: str, tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    source = TESTS / "text_corpus" / f"tables-{case}.odt"
    report = audit_odf(source)
    row = measured(measurement(report, TableMeasurements).table_classifications)[0]
    expected = {"positive": "complex-data", "negative": "ambiguous", "data-no-headers": "data"}
    assert isinstance(row, MeasuredTable)
    assert row.classification == expected[case]
    findings = {finding.rule_id for finding in report.findings}
    if case == "negative":
        assert rules.TABLE001.id in findings
        assert not any(question.kind.id == "table.headers" for question in report.decisions)
        refused = tmp_path / "refused.odt"
        assert_refused(
            apply_answers(source, refused, [header_inputs({"Intent": header_answer(rows=1)})]),
            match="ambiguous.*Writer",
        )
        assert not refused.exists()
    elif case == "data-no-headers":
        assert rules.TABLE003.id in findings
        question = next(q for q in report.decisions if q.kind.id == "table.headers")
        assert question.target is not None
        edited = tmp_path / "headers.odt"
        result = apply_answers(
            source,
            edited,
            [
                header_inputs({
                    question.target.path: header_answer(
                        rows=1, fingerprint=require_target(question.target).fingerprint
                    )
                })
            ],
        )
        assert result.published, result.as_dict()
        source = edited
        assert rules.TABLE003.id not in {f.rule_id for f in audit_odf(source).findings}
    else:
        assert not {rules.TABLE001.id, rules.TABLE002.id, rules.TABLE003.id} & findings
    output = tmp_path / "table.pdf"
    export_document(source, output, Tools(soffice=external_tool("soffice", "libreoffice")))
    assert {finding.rule_id for finding in audit_pdfua(output).findings} == (
        {rules.PDF009.id, rules.PDF016.id} if case == "negative" else {rules.PDF009.id}
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
