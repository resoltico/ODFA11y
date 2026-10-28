# SPDX-License-Identifier: MPL-2.0
"""Core document inspection preserves content dispatch and incremental audit reports."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odfa11y.errors import ToolFailedError
from odfa11y.pipeline import inspection
from odfa11y.pipeline.inspection import audit_document
from odfa11y.report import FactKeys
from tests.fixtures.pdf import tagged_writer
from tests.fixtures.writer import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


def test_core_dispatch_uses_content_and_applies_odf_schema(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    odf = make_minimal_odt(tmp_path / "source.pdf")
    reports = list(audit_document(odf, schema=True, verapdf=True))
    assert len(reports) == 1
    assert reports[0].kind == "odf"
    assert reports[0].facts[FactKeys.SCHEMA_VIOLATION_COUNT] == 0
    assert reports[0].sources == (odf,)
    output = capsys.readouterr()
    assert not output.out
    assert not output.err


def test_core_builtin_pdf_does_not_require_validator(tmp_path: Path) -> None:
    source = tmp_path / "source.odt"
    tagged_writer().write(source)
    reports = list(audit_document(source, schema=True))
    assert [report.kind for report in reports] == ["pdf"]
    assert reports[0].sources == (source,)


def test_core_validator_path_implies_validation_and_missing_tool_is_warning(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pdf"
    tagged_writer().write(source)
    reports = list(audit_document(source, verapdf_path=tmp_path / "absent-validator"))
    assert [report.kind for report in reports] == ["pdf", "verapdf"]
    assert reports[1].findings[0].rule_id == "VERA000"
    assert reports[1].warning_count == 1
    assert reports[1].sources == (source,)


def test_core_retains_completed_pdf_report_when_validator_execution_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.pdf"
    tagged_writer().write(source)

    def failed(*_args: object, **_kwargs: object) -> None:
        message = "native validator failed"
        raise ToolFailedError(message)

    monkeypatch.setattr(inspection, "check_pdfua", failed)
    reports = []
    with pytest.raises(ToolFailedError, match="validator failed"):
        reports.extend(audit_document(source, verapdf=True))
    assert len(reports) == 1
    assert reports[0].kind == "pdf"
    assert reports[0].sources == (source,)


def test_core_progress_contains_no_source_path_or_document_values(tmp_path: Path) -> None:
    source = tmp_path / "private-document.pdf"
    tagged_writer().write(source)
    events: list[tuple[str, str]] = []
    list(
        audit_document(
            source,
            verapdf_path=tmp_path / "absent-validator",
            on_progress=lambda event: events.append((event.step, event.state)),
        )
    )
    assert events == [
        ("audit-document", "running"),
        ("validate-pdf", "running"),
    ]
