# SPDX-License-Identifier: MPL-2.0
"""Render reports and map severities to exit codes."""

from __future__ import annotations

import json

import pytest

from odfa11y.report import AuditReport, Severity, max_severity_exit_code, render_report


def _report() -> AuditReport:
    report = AuditReport(subject="sample.odt", metadata={"title": "T"})
    report.add(
        "TST001",
        Severity.WARNING,
        "Needs review",
        location="content.xml",
        details={"count": 2},
        fixable=True,
    )
    return report


def test_text_report_shows_result_metadata_and_issue_context() -> None:
    lines = render_report(_report()).splitlines()
    assert lines[:3] == [
        "Subject: sample.odt",
        "Result: PASS",
        "Issues: 0 error(s), 1 warning(s), 0 info",
    ]
    assert "  title: T" in lines
    assert any("TST001 [content.xml] (fixable): Needs review" in line for line in lines)
    assert any(line.strip() == "count: 2" for line in lines)


def test_json_report_round_trips_findings() -> None:
    data = json.loads(render_report(_report(), output_format="json"))
    assert data["summary"] == {"errors": 0, "warnings": 1, "info": 0}
    assert data["issues"][0]["rule_id"] == "TST001"
    assert data["issues"][0]["fixable"] is True


def test_unsupported_format_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported report format: yaml"):
        render_report(_report(), output_format="yaml")


@pytest.mark.parametrize(
    ("severity", "strict", "expected"),
    [
        (Severity.INFO, True, 0),
        (Severity.WARNING, False, 0),
        (Severity.WARNING, True, 1),
        (Severity.ERROR, False, 2),
        (Severity.ERROR, True, 2),
    ],
)
def test_exit_codes_follow_highest_severity(
    severity: Severity, *, strict: bool, expected: int
) -> None:
    report = AuditReport(subject="x")
    report.add("TST002", severity, "finding")
    assert max_severity_exit_code(report, strict=strict) == expected
