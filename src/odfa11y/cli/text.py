# SPDX-License-Identifier: MPL-2.0
"""Render typed facts for people and escape untrusted terminal fields."""

import shlex
import textwrap
from collections.abc import Iterable
from dataclasses import fields, is_dataclass

import odfa11y as api
from odfa11y import ExitStatus, Report

BYTE_MAX = 0xFF
BIDI_CONTROLS = frozenset({0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)})

UNSAFE_CONTROLS = frozenset({*range(0x20), *range(0x7F, 0xA0), *BIDI_CONTROLS, 0x2028, 0x2029})


def terminal_text(value: object) -> str:
    """Escape terminal and direction controls while preserving ordinary Unicode.

    Returns
    -------
    str
        One safe field, with control characters represented by visible escapes.

    """
    result = []
    for character in str(value):
        code = ord(character)
        if code in UNSAFE_CONTROLS:
            result.append(f"\\x{code:02x}" if code <= BYTE_MAX else f"\\u{code:04x}")
        else:
            result.append(character)
    return "".join(result)


def _render_text(report: Report) -> str:
    lines = [
        *_field("Subject: ", f"{report.subject} ({report.kind})"),
        (
            f"Findings: {report.error_count} error(s), "
            f"{report.warning_count} warning(s), {report.info_count} info"
        ),
    ]
    if report.findings:
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
            if decision.context is not None:
                context = "; ".join(
                    f"{item.name}={getattr(decision.context, item.name)}"
                    for item in fields(decision.context)
                    if getattr(decision.context, item.name) is not None
                )
                lines.extend(_field("    Context: ", context))
    if report.facts:
        lines.append("Facts:")
        lines.extend(_fact_lines(report))
    return "\n".join(lines)


def _fact_lines(report: Report) -> list[str]:
    lines = []
    for record in report.facts:
        if not is_dataclass(record) or isinstance(record, type):
            message = "Report facts must be dataclass values"
            raise TypeError(message)
        producer = getattr(record, "producer", type(record).__name__)
        for item in fields(record):
            if item.name.startswith("_") or item.name == "producer":
                continue
            value = getattr(record, item.name)
            if value is not None:
                lines.extend(_field(f"  {producer}.{item.name}: ", _summarize(value)))
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


def render_reports(reports: Iterable[Report]) -> str:
    return "\n\n".join(_render_text(report) for report in reports)


def render_verdict(status: int, *, strict: bool = False) -> str:
    value = ExitStatus(status)
    policy = "Errors and warnings fail." if strict else "Errors fail; warnings require review."
    outcome = "passed" if value is ExitStatus.PASSED else "failed"
    return f"Result: {outcome} (exit {value.value}). {value.meaning}\nGate: {policy}"


def remedy_hint(remedy: api.Remedy) -> str:
    target = terminal_text(remedy.target or "the document")
    detail = terminal_text(remedy.detail or "the declared resource")
    match remedy.action:
        case api.RemedyAction.REGENERATE_PLAN:
            return "Next: generate a fresh plan for this source and review its answers."
        case api.RemedyAction.REBIND_PLAN:
            return (
                "Next: use plan NEW_SOURCE --from OLD_PLAN and review answers that no longer match."
            )
        case api.RemedyAction.CHOOSE_OUTPUT:
            return "Next: choose an available destination or explicitly replace a regular file."
        case api.RemedyAction.INSTALL_TOOL:
            return f"Next: install or select {target}."
        case api.RemedyAction.EMBED_RESOURCE:
            return f"Next: embed {detail} for {target} in the source application."
        case api.RemedyAction.EDIT_IN_APPLICATION:
            instruction = terminal_text(remedy.detail or "")
            return f"Next: edit {target} in the source application. {instruction}".rstrip()

    message = "Unhandled remedy action"
    raise ValueError(message)


def audit_next_step(result: api.AuditResult) -> str | None:
    for item in result.inputs:
        if item.plannable and any(report.decisions for report in item.reports):
            source = str(item.source)
            if terminal_text(source) == source:
                return (
                    f"Next: odfa11y plan -- {shlex.quote(source)}\n"
                    "Review the questions before supplying answers."
                )
    return None


def render_remediation(result: api.RemediationResult) -> str:
    lines = []
    for outcome in result.outcomes:
        target = f" [{terminal_text(outcome.target)}]" if outcome.target else ""
        lines += _field(f"- {outcome.status.value} {outcome.kind_id}{target}: ", outcome.message)
        if outcome.failure and outcome.failure.remedy:
            lines.append(remedy_hint(outcome.failure.remedy))
    for prediction in result.predictions:
        resolved = ", ".join(finding.rule_id for finding in prediction.resolved) or "none"
        remaining = ", ".join(finding.rule_id for finding in prediction.remaining) or "none"
        lines += _field(
            f"Prediction {prediction.kind_id}: ", f"resolved {resolved}; remaining {remaining}"
        )
    for question in result.unanswered:
        target = f" at {question.target}" if question.target else ""
        lines += _field(
            f"Unanswered {question.kind_id}{target}: ", question.reason or "No answer supplied"
        )
    lines += [
        terminal_text(f"- {violation.kind}: {violation.message}") for violation in result.violations
    ]
    schema = result.schema
    lines.append(
        f"Schema: {schema.status}; ODF {schema.version}; {schema.before_count} before, "
        f"{schema.after_count} after, {schema.new_count} new"
    )
    match result.publication:
        case api.PublicationState.PUBLISHED:
            lines += _field("Wrote: ", result.destination)
        case api.PublicationState.PREVIEW:
            lines.append("Preview; nothing written.")
        case api.PublicationState.REFUSED:
            lines.append("Not published; review the failed guards.")
    lines.append(render_verdict(result.exit_status))
    return "\n".join(lines)


def _stage_detail(stage: api.StageResult) -> str:
    match stage.outcome:
        case api.Refused(error=error) | api.Crashed(error=error):
            return str(error)
        case api.Skipped(reason=reason, stage=producer):
            return reason.value + (f": {producer.value}" if producer else "")
        case api.NotApplicable(reason=reason):
            return reason
    if stage.report:
        return f"{stage.report.error_count} errors; {stage.report.warning_count} warnings"
    if stage.remediation:
        result = stage.remediation
        return f"{len(result.outcomes)} edit outcomes; schema {result.schema.status}"
    return ""


def render_run(record: api.RunRecord, directory) -> str:
    lines = [f"Profile: {record.profile.value}"]
    for stage in record.stages:
        lines += _field(f"- {stage.name.value}: {stage.outcome.status}; ", _stage_detail(stage))
    lines += _field("Evidence: ", directory)
    lines += _field("Review: ", str(directory) + "/REVIEW.md")
    lines.append(render_verdict(record.exit_status, strict=record.strict))
    return "\n".join(lines)


def render_batch(record: api.BatchRecord, directory) -> str:
    lines = [f"Profile: {record.profile.value}"]
    for item in record.items:
        lines += _field(
            f"- {item.id}: {item.status}; ",
            f"exit {item.exit_status}; stage {item.failed_stage}; evidence {item.evidence}",
        )
        if item.error:
            lines += _field("  Reason: ", item.error.message)
    lines += _field("Evidence: ", directory)
    lines.append(render_verdict(record.exit_status, strict=record.profile.strict))
    return "\n".join(lines)


def render_doctor(info: api.DoctorResult) -> str:
    lines = [f"odfa11y: {info.odfa11y}; Python: {info.python}", f"Platform: {info.platform}"]
    lines += [f"{name}: {version}" for name, version in info.libraries.items()]
    for tool in (info.toolchain.libreoffice, info.toolchain.verapdf):
        if tool:
            lines.append(f"{tool.name}: {tool.version}")
    for unavailable in info.unavailable:
        lines += _field(f"{unavailable.tool} unavailable: ", "; ".join(unavailable.blocks))
        lines.append(f"Select with --{unavailable.selection} PATH.")
    for result in info.capabilities:
        lines += _field(f"{result.id.value}: {result.status.value}; ", result.meaning)
        lines += _field("  Related rules: ", ", ".join(result.related_rules))
        if result.reason:
            lines += _field("  Reason: ", result.reason)
    lines.append(render_verdict(info.exit_status))
    lines.append("Scope: dependency identities and scoped experiments; no conformance verdict.")
    return "\n".join(lines)
