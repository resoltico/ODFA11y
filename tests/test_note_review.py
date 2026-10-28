# SPDX-License-Identifier: MPL-2.0
"""Footnotes and page annotations consistently require review under strict acceptance."""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.report import Report, Severity, exit_status
from odfa11y.source_audit import audit_odf

ROOT = Path(__file__).parent


@pytest.mark.parametrize("family", ["text", "presentation", "drawing"])
def test_notes_warn_consistently_and_fail_strict_acceptance(tmp_path: Path, family: str) -> None:
    if family == "text":
        source = ROOT / "corpus/footnotes.odt"
    else:
        suffix = ".odp" if family == "presentation" else ".odg"
        document = OdfDocument.open(ROOT / "family_corpus" / (f"fruit-{family}" + suffix))
        baseline = validate(document)
        [page] = select_elements(document.tree(Part.CONTENT), "//draw:page")
        annotation = etree.SubElement(page, qn("office", "annotation"))
        etree.SubElement(annotation, qn("text", "p")).text = "Review this relationship."
        source = document.save(tmp_path / ("notes" + suffix))
        assert validate(OdfDocument.open(source)).count == baseline.count
    observed = audit_odf(source)
    notes = [finding for finding in observed.findings if finding.rule_id == "NOTE001"]
    assert notes
    assert all(finding.severity == Severity.WARNING for finding in notes)
    scope = Report(kind="odf", subject=source.name, findings=notes)
    assert exit_status([scope], strict=True) == 1
    assert exit_status([scope], strict=False) == 0
