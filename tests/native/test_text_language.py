# SPDX-License-Identifier: MPL-2.0
"""Writer retains language-tagged text and exports explicit paragraph/inline language tags."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pypdf import PdfReader

from odfa11y import plan, remediate
from odfa11y.odf import OdfDocument, validate
from odfa11y.pipeline.native import export_document
from odfa11y.report import FactKeys
from odfa11y.source_audit import audit_odf
from odfa11y.tools import Tools
from tests.fixtures.paths import TESTS
from tests.fixtures.plans import plan_header

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.mark.integration
@pytest.mark.parametrize("case", ["positive", "negative"])
def test_writer_language_source_decision_and_pdf_tags(
    case: str, tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    source = TESTS / "text_corpus" / f"language-{case}.odt"
    report = audit_odf(source)
    assert ("LANG004" in {finding.rule_id for finding in report.findings}) is (case == "negative")
    if case == "negative":
        question = next(q for q in plan(source).report.decisions if q.kind.id == "language.target")
        assert question.target is not None
        answers = tmp_path / "language.toml"
        answers.write_text(
            plan_header(source)
            + f'\n[decisions."language.target"."{question.target.path}"]\n'
            + f'fingerprint = "{question.fingerprint}"\nwestern = "fr-FR"\n'
        )
        edited = tmp_path / "reviewed.odt"
        result = remediate(source, edited, answers)
        assert result.published, result.as_dict()
        assert validate(OdfDocument.open(edited)).count == validate(OdfDocument.open(source)).count
        source = edited
        report = audit_odf(source)
    rows = report.facts[FactKeys.TEXT_EFFECTIVE_LANGUAGES]
    assert any(row.get("western") == "fr-FR" for row in rows)
    output = tmp_path / "language.pdf"
    export_document(source, output, Tools(soffice=external_tool("soffice", "libreoffice")))
    reader = PdfReader(output)
    assert "Bonjour." in "\n".join(page.extract_text() for page in reader.pages)
    pending = [reader.root_object["/StructTreeRoot"]]
    languages = []
    while pending:
        node = pending.pop().get_object()
        if not isinstance(node, dict):
            continue
        if value := node.get("/Lang"):
            languages.append(str(value))
        kids = node.get("/K", [])
        pending.extend(kids if isinstance(kids, list) else [kids])
    assert "fr-FR" in languages
