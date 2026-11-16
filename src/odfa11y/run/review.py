# SPDX-License-Identifier: MPL-2.0
"""Put outstanding human work before gates and source-to-candidate facts."""

import json

from odfa11y.contracts import JsonValue, record_dict
from odfa11y.progress import Stage
from odfa11y.status import Crashed, GateFailed, NotApplicable, Passed, Refused, Skipped
lazy from odfa11y.evidence.redact import Redactor
lazy from odfa11y.run.record import RunRecord, StageResult

NOT_VALIDATION = (
    "veraPDF did not run: the built-in PDF checks are a smoke test, not PDF/UA validation."
)


def render_review(record: RunRecord, *, redactor: Redactor | None = None) -> str:
    """Render outstanding decisions, observed review topics and facts without duplicate audits."""
    lines = [f"# Review sheet: {_cell(record.document.name)}", "", "## Needs a human", ""]
    lines += _attention(record, redactor) or [
        "- No outstanding machine finding or unanswered decision."
    ]
    lines += ["", "## Human review still required", ""]
    lines += [f"- [ ] {item.text}" for item in record.human_review]
    validator = next((stage for stage in record.stages if stage.name == Stage.VALIDATE_PDF), None)
    if validator is None or not isinstance(validator.outcome, Passed):
        caveat = (
            "veraPDF did not pass: PDF/UA conformance was not established."
            if validator and isinstance(validator.outcome, GateFailed | Refused | Crashed)
            else NOT_VALIDATION
        )
        lines += ["", f"> {caveat}"]
    lines += [
        "",
        "## Gates",
        "",
        f"Assurance profile: `{record.profile.value}`",
        "",
        f"Automated gates: **{record.status.upper()}**"
        + (f" (failed at `{record.failed_stage}`)" if record.failed_stage else ""),
        "",
        "| Stage | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for stage in record.stages:
        detail = _detail(stage)
        if redactor:
            detail = redactor.text(detail)
        lines.append(f"| `{stage.name}` | {stage.outcome.status} | {_cell(detail)} |")
    lines += ["", "## Machine-established facts", "", *_facts(record, redactor)]
    return "\n".join(lines) + "\n"


def _detail(stage: StageResult) -> str:
    match stage.outcome:
        case Refused(error=error) | Crashed(error=error):
            return str(error)
        case Skipped(reason=reason, stage=producer):
            return f"{reason.value}" + (f": {producer}" if producer else "")
        case NotApplicable(reason=reason):
            return reason
    if stage.report:
        return f"{stage.report.error_count} error(s), {stage.report.warning_count} warning(s)"
    if stage.remediation:
        result = stage.remediation
        return f"{len(result.outcomes)} outcome(s); schema: {result.schema.status}"
    return ""


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("\\", "\\\\").replace("|", "\\|")


def _measurements(stage: StageResult | None) -> dict[str, JsonValue]:
    result = {}
    if stage and stage.report:
        for facts in stage.report.facts:
            values = record_dict(facts)
            producer = values.pop("producer")
            result.update({f"{producer}.{key}": value for key, value in values.items()})
    return result


def _facts(record: RunRecord, redactor: Redactor | None) -> list[str]:
    stages = {stage.name: stage for stage in record.stages}
    source = _measurements(stages.get(Stage.AUDIT_SOURCE))
    candidate = _measurements(stages.get(Stage.AUDIT_REMEDIATED))
    if redactor:
        source = redactor.record(source)
        candidate = redactor.record(candidate)
    facts = [
        f"- {key}: {_value(source.get(key))} → {_value(candidate.get(key))}"
        for key in sorted(source.keys() | candidate.keys())
    ]
    for name in (Stage.AUDIT_PDF, Stage.VALIDATE_PDF, Stage.FIDELITY):
        measurements = _measurements(stages.get(name))
        if redactor:
            measurements = redactor.record(measurements)
        facts += [f"- `{name}` {key}: {_value(value)}" for key, value in measurements.items()]
    return facts or ["- No stage produced facts."]


def _value(value: JsonValue) -> str:
    return "unmeasured" if value is None else json.dumps(value, ensure_ascii=False)


def _attention(record: RunRecord, redactor: Redactor | None) -> list[str]:
    lines = []
    candidate_exists = any(
        stage.name == Stage.AUDIT_REMEDIATED and stage.report for stage in record.stages
    )
    for stage in record.stages:
        if isinstance(stage.outcome, Refused | Crashed):
            detail = str(stage.outcome.error)
            if redactor:
                detail = redactor.text(detail)
            lines.append(f"- `{stage.name}`: {_cell(detail)}")
        if stage.report and (stage.name != Stage.AUDIT_SOURCE or not candidate_exists):
            lines += [
                f"- `{stage.name}` {finding.severity.value} {finding.rule_id}: {finding.message}"
                for finding in stage.report.findings
                if finding.severity.value in {"error", "warning"}
            ]
        if stage.remediation:
            lines += [
                f"- Unanswered: `{item.kind_id}`" + (f" at `{item.target}`" if item.target else "")
                for item in stage.remediation.unanswered
            ]
    return lines
