# SPDX-License-Identifier: MPL-2.0
"""Render reports as text, JSON or SARIF and map them to exit statuses."""

import json
import textwrap
lazy from collections.abc import Iterable
lazy from pathlib import Path

from odfa11y.contracts import record_dict
from odfa11y.errors import InvalidOption
from odfa11y.report.sarif import sarif_log
from odfa11y.report.terminal import terminal_text
from odfa11y.status import ExitStatus, combine_statuses, gate_outcome
lazy from odfa11y.report.model import Report

FORMATS = ("text", "json", "sarif")


def render_reports(
    reports: Iterable[Report], *, output_format: str = "text", source_root: Path | None = None
) -> str:
    """Render one or more reports; JSON is a single object for one report, else an array.

    Delegated SARIF path resolution raises PackageError for unavailable sources.

    Returns
    -------
    str
        The formatted reports.

    Raises
    ------
    InvalidOption
        The requested format is unsupported or SARIF source identities are unsafe.

    """
    items = list(reports)
    if output_format == "sarif":
        if source_root is None:
            msg = "SARIF requires an explicit source root."
            raise InvalidOption(msg)
        return json.dumps(sarif_log(items, source_root=source_root), indent=2, ensure_ascii=False)
    if output_format == "json":
        payload = items[0].as_dict() if len(items) == 1 else [r.as_dict() for r in items]
        return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
    if output_format != "text":
        msg = f"Unsupported report format: {output_format}"
        raise InvalidOption(msg)
    return "\n\n".join(_render_text(report) for report in items)


def exit_status(reports: Iterable[Report], *, strict: bool = False) -> ExitStatus:
    """Map findings to a command exit status: 2 for errors, 1 for strict warnings.

    Returns
    -------
    int
        Zero on success, 1 when strict and a warning exists, or 2 when an error exists.

    """
    return combine_statuses(
        gate_outcome(report, strict=strict).exit_status(strict) for report in reports
    )


def _render_text(report: Report) -> str:
    lines = [
        *_field("Subject: ", f"{report.subject} ({report.kind})"),
        f"Check: {'errors found' if report.error_count else 'no errors'}",
        (
            f"Findings: {report.error_count} error(s), "
            f"{report.warning_count} warning(s), {report.info_count} info"
        ),
    ]
    if report.findings:
        lines.append("Findings:")
        for finding in report.findings:
            lines.extend(
                _field(f"  {finding.severity.value.upper()} {finding.rule_id}: ", finding.message)
            )
            if finding.location:
                lines.extend(_field("    location: ", finding.location.label))
            for key, value in finding.details.items():
                lines.extend(_field(f"    {terminal_text(key)}: ", value))
    if report.decisions:
        lines.append("Open decisions:")
        for decision in report.decisions:
            target = decision.target.path if decision.target else "document"
            lines.extend(_field(f"  {decision.kind.id}: ", target))
    if report.facts:
        lines.append("Facts:")
        lines.extend(_fact_lines(report))
    return "\n".join(lines)


def _fact_lines(report: Report) -> list[str]:
    lines: list[str] = []
    for record in report.facts:
        values = record_dict(record)
        producer = str(values.pop("producer"))
        for name, value in values.items():
            if value is not None:
                lines.extend(_field(f"  {producer}.{name}: ", _summarize(value)))
    return lines


def _field(label: str, value: object) -> list[str]:
    label = terminal_text(label)
    return textwrap.wrap(
        terminal_text(value),
        width=80,
        initial_indent=label,
        subsequent_indent=" " * min(len(label), 12),
        break_long_words=False,
        break_on_hyphens=False,
    ) or [label.rstrip()]


def _summarize(value: object) -> str:
    if isinstance(value, list):
        return f"{len(value)} record(s)"
    return str(value)
