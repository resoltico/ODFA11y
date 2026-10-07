# SPDX-License-Identifier: MPL-2.0
"""Render reports as text, JSON or SARIF and map them to exit statuses."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .sarif import sarif_log

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from .models import Report

FORMATS = ("text", "json", "sarif")
EXIT_STRICT_WARNINGS = 1
EXIT_ERRORS = 2


def render_reports(
    reports: Iterable[Report], *, output_format: str = "text", source_root: Path | None = None
) -> str:
    """Render one or more reports; JSON is a single object for one report, else an array.

    Returns
    -------
    str
        The formatted reports.

    Raises
    ------
    ValueError
        The requested format is unsupported or SARIF source identities are unsafe.

    """
    items = list(reports)
    if output_format == "sarif":
        if source_root is None:
            msg = "SARIF requires an explicit source root."
            raise ValueError(msg)
        return json.dumps(sarif_log(items, source_root=source_root), indent=2, ensure_ascii=False)
    if output_format == "json":
        payload = items[0].as_dict() if len(items) == 1 else [r.as_dict() for r in items]
        return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
    if output_format != "text":
        msg = f"Unsupported report format: {output_format}"
        raise ValueError(msg)
    return "\n\n".join(_render_text(report) for report in items)


def exit_status(reports: Iterable[Report], *, strict: bool = False) -> int:
    """Map findings to a command exit status: 2 for errors, 1 for strict warnings.

    Returns
    -------
    int
        Zero on success, 1 when strict and a warning exists, or 2 when an error exists.

    """
    status = 0
    for report in reports:
        if report.error_count:
            return EXIT_ERRORS
        if strict and report.warning_count:
            status = EXIT_STRICT_WARNINGS
    return status


def _render_text(report: Report) -> str:
    lines = [
        f"Subject: {report.subject} ({report.kind})",
        f"Result: {'PASS' if report.passed else 'FAIL'}",
        (
            f"Findings: {report.error_count} error(s), "
            f"{report.warning_count} warning(s), {report.info_count} info"
        ),
    ]
    if report.metadata:
        lines.append("Metadata:")
        lines.extend(
            f"  {key}: {_summarize(report.metadata[key])}" for key in sorted(report.metadata)
        )
    if report.findings:
        lines.append("Findings:")
        for finding in report.findings:
            where = f" at {finding.location.label}" if finding.location else ""
            lines.append(
                f"  {finding.severity.value.upper():7} {finding.rule_id}{where}: {finding.message}"
            )
            if finding.remedy:
                lines.append(f"           remedy: {finding.remedy}")
            lines.extend(f"           {key}: {value}" for key, value in finding.details.items())
    return "\n".join(lines)


def _summarize(value: object) -> str:
    if isinstance(value, list):
        return f"{len(value)} record(s)"
    return str(value)
