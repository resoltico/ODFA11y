# SPDX-License-Identifier: MPL-2.0
"""Core document inspection preserves content dispatch and incremental audit reports."""

from dataclasses import replace
lazy from pathlib import Path

import pytest

from odfa11y.application.native import NativeTools
from odfa11y.audit.package import PackageMeasurements
from odfa11y.errors import ToolFailure, ToolUnavailable
from odfa11y.run.inspection import audit_document
from tests.fixtures.measurements import measured, measurement
from tests.fixtures.native import validation_result
from tests.fixtures.pdf import tagged_writer
from tests.fixtures.writer import make_minimal_odt


def test_core_dispatch_uses_content_and_applies_odf_schema(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    odf = make_minimal_odt(tmp_path / "source.pdf")
    reports = list(audit_document(odf, schema=True, verapdf=True))
    assert len(reports) == 1
    assert reports[0].kind == "odf"
    assert measured(measurement(reports[0], PackageMeasurements).violation_count) == 0
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


def test_requested_core_validation_requires_the_validator(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    tagged_writer().write(source)
    reports = []
    with pytest.raises(ToolUnavailable):
        reports.extend(
            audit_document(source, verapdf=True, verapdf_path=tmp_path / "absent-validator")
        )
    assert [report.kind for report in reports] == ["pdf"]


def test_core_retains_completed_pdf_report_when_validator_execution_fails(
    native_tools: NativeTools,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.pdf"
    tagged_writer().write(source)

    def failed(*_args: object, **_kwargs: object) -> None:
        message = "native validator failed"
        raise ToolFailure(message)

    native_tools = replace(native_tools, validate=failed)
    reports = []
    with pytest.raises(ToolFailure, match="validator failed"):
        reports.extend(audit_document(source, verapdf=True, native_tools=native_tools))
    assert len(reports) == 1
    assert reports[0].kind == "pdf"
    assert reports[0].sources == (source,)


def test_core_progress_contains_no_source_path_or_document_values(
    native_tools: NativeTools, tmp_path: Path
) -> None:
    source = tmp_path / "private-document.pdf"
    tagged_writer().write(source)
    events: list[tuple[str, str]] = []
    native_tools = replace(native_tools, validate=lambda *_args, **_kwargs: validation_result())
    list(
        audit_document(
            source,
            verapdf_path=tmp_path / "absent-validator",
            on_progress=lambda event: events.append((event.step, event.state)),
            native_tools=native_tools,
        )
    )
    assert events == [
        ("audit-document", "running"),
        ("validate-pdf", "running"),
    ]
