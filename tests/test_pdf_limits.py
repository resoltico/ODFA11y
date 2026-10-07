# SPDX-License-Identifier: MPL-2.0
"""PDF size, page-count and structure limits are enforced at their inspection boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odfa11y import pdf_limits
from odfa11y.errors import ToolFailedError
from odfa11y.fidelity import FidelityPolicy, compare_pdfs
from odfa11y.pdf import audit_pdfua, list_fonts
from odfa11y.pdf import structure_walk as walk

from .pdf_fixtures import tagged_writer, text_pdf

if TYPE_CHECKING:
    from pathlib import Path


def test_an_oversized_pdf_is_a_finding_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = text_pdf(tmp_path / "a.pdf", [["x"]])
    monkeypatch.setattr(pdf_limits, "MAX_PDF_BYTES", 10)

    def parse(_stream: object, *, strict: bool) -> None:
        pytest.fail(f"PDF parser invoked for an oversized file (strict={strict})")

    monkeypatch.setattr("odfa11y.pdf.audit.PdfReader", parse)
    report = audit_pdfua(path)
    assert [f.rule_id for f in report.findings] == ["PDF000"]
    assert "exceeds" in report.findings[0].message
    with pytest.raises(ToolFailedError, match="exceeds"):
        compare_pdfs(path, path, FidelityPolicy())


def test_a_pdf_with_too_many_pages_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = text_pdf(tmp_path / "a.pdf", [["x"], ["y"], ["z"]])
    monkeypatch.setattr(pdf_limits, "MAX_PDF_PAGES", 2)
    assert "pages" in audit_pdfua(path).findings[0].message
    with pytest.raises(ToolFailedError, match="3 pages"):
        compare_pdfs(path, path, FidelityPolicy())


def test_a_structure_tree_above_the_limit_is_a_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "tagged.pdf"
    tagged_writer(["H1", "P", "P"]).write(path)
    monkeypatch.setattr(walk, "MAX_STRUCTURE_NODES", 2)
    report = audit_pdfua(path)
    assert [f.rule_id for f in report.findings] == ["PDF000"]
    assert "more than 2 elements" in report.findings[0].message


def test_fonts_are_listed_with_their_embedding(tmp_path: Path) -> None:
    path = text_pdf(tmp_path / "a.pdf", [["x"]])
    assert list_fonts(path) == [{"name": "Helvetica", "embedded": False}]
    assert list_fonts(tmp_path / "absent.pdf") == []
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a pdf")
    assert list_fonts(broken) == []
