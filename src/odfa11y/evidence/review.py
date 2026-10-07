# SPDX-License-Identifier: MPL-2.0
"""Write the human-readable review sheet: facts, gates and what a person must still decide."""

from __future__ import annotations

from typing import Any

HUMAN_REVIEW_ITEMS = (
    ("headings", "Whether each heading names its section and the hierarchy reflects the document."),
    ("alt text", "Whether every graphic's description is meaningful in its context."),
    (
        "reading order",
        "Whether the reading order, including footnotes and floating objects, is logical.",
    ),
    ("table headers", "Whether table header cells describe the data relationships correctly."),
    ("link purpose", "Whether each link's purpose is understandable from its text and context."),
    ("colour", "Whether colour conveys information that is not available any other way."),
    ("layout", "Whether the pages look right: typography, pagination and visual appearance."),
)
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
        f"# Review sheet: {record['input']['name']}",
        "",
        f"Result: **{record['status'].upper()}**"
        + (f" (failed at `{record['failed_stage']}`)" if record["failed_stage"] else ""),
        "",
        "## Gates",
        "",
        "| Stage | Status | Detail |",
        "| --- | --- | --- |",
    ]
    lines += [
        f"| `{stage['name']}` | {stage['status']} | {stage.get('reason') or _summary(stage)} |"
        for stage in stages
    ]
    lines += ["", "## Machine-established facts", ""]
    lines += _facts(stages) or ["- No stage produced facts."]
    attention = _attention(stages)
    if attention:
        lines += ["", "## Findings that need attention", "", *attention]
    verapdf = next((s for s in stages if s["name"] == "verapdf"), None)
    if verapdf is None or verapdf["status"] != "passed":
        lines += ["", f"> {NOT_VALIDATION}"]
    lines += ["", "## Human review still required", ""]
    lines += [f"- [ ] {text}" for _key, text in HUMAN_REVIEW_ITEMS]
    return "\n".join(lines) + "\n"


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
