# SPDX-License-Identifier: MPL-2.0
"""Reporting for ODF accessibility workflows."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .models import AuditReport

if TYPE_CHECKING:
    from collections.abc import Iterable


def render_report(report: AuditReport, *, output_format: str = "text") -> str:
    """Render findings and metadata as text or JSON.

    Returns
    -------
    str
        The formatted report.

    Raises
    ------
    ValueError
        The requested output format is unsupported.

    """
    if output_format == "json":
        return json.dumps(report.as_dict(), indent=2, ensure_ascii=False, sort_keys=True)
    if output_format != "text":
        msg = f"Unsupported report format: {output_format}"
        raise ValueError(msg)

    lines = [
        f"Subject: {report.subject}",
        f"Result: {'PASS' if report.passed else 'FAIL'}",
        (
            f"Issues: {report.error_count} error(s), "
            f"{report.warning_count} warning(s), {report.info_count} info"
        ),
    ]
    if report.metadata:
        lines.append("Metadata:")
        for key in sorted(report.metadata):
            value = report.metadata[key]
            if key == "paragraph_styles":
                lines.append(f"  {key}: {len(value)} style record(s)")
            else:
                lines.append(f"  {key}: {value}")
    if report.issues:
        lines.append("Issues:")
        for issue in report.issues:
            loc = f" [{issue.location}]" if issue.location else ""
            fix = " (fixable)" if issue.fixable else ""
            lines.append(
                f"  {issue.severity.value.upper():7} {issue.rule_id}{loc}{fix}: {issue.message}"
            )
            if issue.details:
                for key, value in issue.details.items():
                    lines.append(f"           {key}: {value}")
    return "\n".join(lines)


def max_severity_exit_code(report: AuditReport, *, strict: bool = False) -> int:
    """Map errors and optionally warnings to command exit codes.

    Returns
    -------
    int
        Zero on success, 1 for strict warnings, or 2 for errors.

    """
    if report.error_count:
        return 2
    if strict and report.warning_count:
        return 1
    return 0


def merge_reports(subject: str, reports: Iterable[AuditReport]) -> AuditReport:
    """Combine findings while retaining each subject's metadata.

    Returns
    -------
    AuditReport
        Combined findings and per-subject metadata.

    """
    merged = AuditReport(subject=subject)
    for report in reports:
        merged.issues.extend(report.issues)
        merged.metadata[report.subject] = report.metadata
    return merged
