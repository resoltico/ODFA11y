# SPDX-License-Identifier: MPL-2.0
"""Write the human-readable review sheet: facts, gates and what a person must still decide."""

from __future__ import annotations

from typing import Any

NOT_VALIDATION = (
    "veraPDF did not run: the built-in PDF checks are a smoke test, not PDF/UA validation."
)


def render_review(record: dict[str, Any]) -> str:
    """Render REVIEW.md for a run record.

    Returns
    -------
    str
        Markdown separating machine-established facts from decisions left to a person.

    """
    stages = record["stages"]
    lines = [
        f"# Review sheet: {record['document']['name']}",
        "",
        f"Result: **{record['status'].upper()}**"
        + (f" (failed at `{record['failed_stage']}`)" if record["failed_stage"] else ""),
        "",
        "## Gates",
        "",
        "| Stage | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for stage in stages:
        detail = _cell(stage.get("reason") or _summary(stage))
        lines.append(f"| `{stage['name']}` | {stage['status']} | {detail} |")
    lines += ["", "## Machine-established facts", ""]
    lines += _facts(stages) or ["- No stage produced facts."]
    attention = _attention(stages)
    if attention:
        lines += ["", "## Findings that need attention", "", *attention]
    verapdf = next((s for s in stages if s["name"] == "verapdf"), None)
    if verapdf is None or verapdf["status"] != "passed":
        lines += ["", f"> {NOT_VALIDATION}"]
    lines += ["", "## Human review still required", ""]
    lines += [f"- [ ] {item['text']}" for item in record["human_review"]]
    return "\n".join(lines) + "\n"


def _cell(text: str) -> str:
    """Make text safe inside one Markdown table cell.

    Returns
    -------
    str
        The text on one line with backslashes and pipes escaped.

    """
    return " ".join(text.split()).replace("\\", "\\\\").replace("|", "\\|")


def _summary(stage: dict[str, Any]) -> str:
    report = stage.get("report")
    if report:
        summary = report["summary"]
        return f"{summary['errors']} error(s), {summary['warnings']} warning(s)"
    remediation = stage.get("remediation")
    if remediation:
        return f"{len(remediation['outcomes'])} outcome(s); schema: {remediation['schema_check']}"
    return ""


def _facts(stages: list[dict[str, Any]]) -> list[str]:
    facts = []
    for stage in stages:
        report = stage.get("report")
        if not report or not report["metadata"]:
            continue
        for key, value in sorted(report["metadata"].items()):
            if isinstance(value, (str, int, float, bool)):
                facts.append(f"- `{stage['name']}` {key}: {value}")
    return facts


def _attention(stages: list[dict[str, Any]]) -> list[str]:
    lines = []
    for stage in stages:
        report = stage.get("report")
        if not report:
            continue
        lines += [
            f"- `{stage['name']}` {finding['severity']} {finding['rule_id']}: {finding['message']}"
            for finding in report["findings"]
            if finding["severity"] in {"error", "warning"}
        ]
    return lines
