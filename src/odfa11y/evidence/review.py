# SPDX-License-Identifier: MPL-2.0
"""Render typed run facts, gate outcomes and outstanding human review."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.outcomes import StageName, StageStatus

if TYPE_CHECKING:
    from odfa11y.pipeline.record import RunRecord, StageResult

    from .redact import Redactor

NOT_VALIDATION = (
    "veraPDF did not run: the built-in PDF checks are a smoke test, not PDF/UA validation."
)


def render_review(record: RunRecord, *, redactor: Redactor | None = None) -> str:
    """Render REVIEW.md without interpreting serialized dictionary keys.

    Returns
    -------
    str
        Markdown separating measured facts from required human decisions.

    """
    lines = [
        f"# Review sheet: {record.document.name}",
        "",
        f"Automated gates: **{record.status.upper()}**"
        + (f" (failed at `{record.failed_stage}`)" if record.failed_stage else ""),
        "",
        "## Gates",
        "",
        "| Stage | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for stage in record.stages:
        detail = stage.reason or _summary(stage)
        if redactor is not None:
            detail = redactor.text(detail)
        detail = _cell(detail)
        lines.append(f"| `{stage.name}` | {stage.status} | {detail} |")
    lines += ["", f"Assurance profile: `{record.profile.name}`"]
    lines += ["", "## Machine-established facts", ""]
    lines += _facts(record.stages) or ["- No stage produced facts."]
    attention = _attention(record.stages)
    if attention:
        lines += ["", "## Findings that need attention", "", *attention]
    validator = next(
        (stage for stage in record.stages if stage.name == StageName.VALIDATE_PDF), None
    )
    if validator is None or validator.status != StageStatus.PASSED:
        caveat = NOT_VALIDATION
        if validator is not None and validator.status == StageStatus.FAILED:
            caveat = (
                "veraPDF did not pass: PDF/UA conformance was not established. "
                "Review the validator findings or execution failure above."
            )
        lines += ["", f"> {caveat}"]
    lines += ["", "## Human review still required", ""]
    lines += [f"- [ ] {item.text}" for item in record.human_review]
    return "\n".join(lines) + "\n"


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("\\", "\\\\").replace("|", "\\|")


def _summary(stage: StageResult) -> str:
    if stage.report:
        return f"{stage.report.error_count} error(s), {stage.report.warning_count} warning(s)"
    if stage.remediation:
        result = stage.remediation
        return f"{len(result.outcomes)} outcome(s); schema: {result.schema.status}"
    return ""


def _facts(stages: list[StageResult]) -> list[str]:
    facts = []
    for stage in stages:
        if stage.report:
            for key in sorted(stage.report.facts, key=lambda item: item.id):
                value = stage.report.facts[key]
                if isinstance(value, (str, int, float, bool)):
                    facts.append(f"- `{stage.name}` {key.id}: {value}")
    return facts


def _attention(stages: list[StageResult]) -> list[str]:
    return [
        f"- `{stage.name}` {finding.severity.value} {finding.rule_id}: {finding.message}"
        for stage in stages
        if stage.report
        for finding in stage.report.findings
        if finding.severity.value in {"error", "warning"}
    ]
