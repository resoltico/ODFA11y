# SPDX-License-Identifier: MPL-2.0
"""One strict plan codec derives parsing, templates and schema from registered answers."""

import dataclasses
import json
import tomllib
from pathlib import Path
from typing import cast, get_type_hints
lazy from collections.abc import Iterable, Mapping

from odfa11y.contracts import decode, fields_of, record_dict, schema_for
from odfa11y.decisions import DecisionScope
from odfa11y.errors import DocumentRefusal, IoFailure, PlanError
from odfa11y.evidence.redact import Redactor
from odfa11y.plans.contracts import PlanFile, decision_contract, file_contract, from_file
from odfa11y.plans.model import PLAN_SCHEMA_VERSION, Plan, PlanHeader
from odfa11y.targets import (
    Fingerprint,
    TargetPath,
    require_target,
)
lazy from odfa11y.contracts import JsonObject
lazy from odfa11y.decisions import Decision, DecisionKind, OpenDecision
lazy from odfa11y.decisions.decision import QuestionContext
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.plans.fidelity import FidelityPolicy
lazy from odfa11y.report import Finding


def parse_plan(
    path: str | Path,
    kinds: Mapping[str, DecisionKind],
    *,
    document: OdfDocument | None = None,
    source_sha256: str | None = None,
) -> Plan:
    """Read one source-bound TOML plan, with no accepted legacy tables.

    Returns
    -------
    Plan
        Validated answers and fidelity policy.

    Raises
    ------
    PlanError
        The file is unreadable, malformed or violates a registered contract.

    """
    try:
        with Path(path).open("rb") as stream:
            values = tomllib.load(stream)
    except OSError as error:
        raise IoFailure.from_oserror(error) from error
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        msg = f"Cannot read plan: {exc}"
        raise PlanError(msg) from exc
    return parse_tables(values, kinds, document=document, source_sha256=source_sha256)


def parse_tables(
    values: Mapping[str, object],
    kinds: Mapping[str, DecisionKind],
    *,
    document: OdfDocument | None = None,
    source_sha256: str | None = None,
) -> Plan:
    """Validate the plan's binding and answer tables against declared kinds.

    Returns
    -------
    Plan
        A bound plan, without executing any operation.

    Raises
    ------
    PlanError
        A table, decision kind, target or answer is invalid.

    """
    header = values.get("plan")
    if isinstance(header, Mapping) and "format" in header:
        message = "This plan uses a retired header; generate a fresh plan with schema_version = 1."
        raise PlanError(message)
    contract = file_contract(kinds)
    try:
        record = cast(
            PlanFile[Mapping[str, object]], decode(contract, values, label="plan", error=PlanError)
        )
        return from_file(record, kinds)
    except PlanError as error:
        problems = list(error.problems or (error.message,))
        if document is not None:
            problems.extend(_raw_binding_problems(values, kinds, document))
        header = values.get("plan")
        binding = header.get("source") if isinstance(header, Mapping) else None
        if (
            source_sha256 is not None
            and isinstance(binding, Mapping)
            and isinstance(binding.get("sha256"), str)
            and binding["sha256"] != source_sha256
        ):
            problems.append(
                "Plan/source digest mismatch; create a newly bound plan with plan --from."
            )
        message = "Plan contains invalid answers or source bindings"
        raise PlanError(message, problems=tuple(dict.fromkeys(problems))) from error


def _raw_binding_problems(
    values: Mapping[str, object], kinds: Mapping[str, DecisionKind], document: OdfDocument
) -> list[str]:
    """Inspect only independently well-formed identities after answer decoding failed."""
    problems = []
    tables = values.get("decisions")
    if not isinstance(tables, Mapping):
        return problems
    for kind_id, entries in tables.items():
        kind = kinds.get(kind_id)
        if kind is None or kind.domain is None or not isinstance(entries, Mapping):
            continue
        for path, fields in entries.items():
            if not isinstance(fields, Mapping) or not (fields.keys() - {"fingerprint"}):
                continue
            try:
                target_path = TargetPath(path)
                expected = Fingerprint(fields.get("fingerprint"))
            except PlanError:
                continue  # The contract decoder already reports malformed identities.
            try:
                current = kind.domain.binding(document, target_path)
                if current.fingerprint != expected:
                    problems.append(f"{kind.id} @ {path}: fingerprint mismatch")
            except (PlanError, DocumentRefusal) as error:
                problems.append(f"{kind.id} @ {path}: {error.message}")
    return problems


def render_plan(
    header: PlanHeader,
    decisions: Iterable[OpenDecision],
    *,
    findings: Iterable[Finding] = (),
    optional: Iterable[OpenDecision] = (),
    answers: Iterable[Decision] = (),
    not_carried: Iterable[tuple[Decision, str]] = (),
    fidelity: FidelityPolicy | None = None,
) -> str:
    """Print the binding header and disabled, reviewable answers with shared field help.

    Returns
    -------
    str
        TOML with active binding metadata and inert question blocks.

    """
    lines = [
        "# Review each answer before enabling it; this file does not change a source by itself.",
        "[plan]",
        f"schema_version = {PLAN_SCHEMA_VERSION}",
        f"generator = {json.dumps(header.generator)}",
        f"source.sha256 = {json.dumps(header.source.sha256)}",
        "",
    ]
    findings = tuple(findings)
    redactor = Redactor(())
    decisions = tuple(decisions)
    if any(not question.rules for question in decisions):
        message = "Questions without raised findings belong in the optional overrides section"
        raise PlanError(message)
    answered = {
        (answer.kind.id, answer.target.path if answer.target else None): answer
        for answer in answers
    }
    for index, decision in enumerate((*decisions, *optional)):
        if index == len(decisions):
            lines += ["# Optional overrides (no finding raised)", ""]
        kind = decision.kind
        key = "decisions." + json.dumps(kind.id)
        if decision.target is not None:
            key += "." + json.dumps(decision.target.path)
        lines.extend(_finding_comments(decision, findings, redactor))
        if decision.context is not None:
            lines.append(_context_comment(decision.context, redactor))
        lines += [f"[{key}]"]
        if decision.current:
            lines.append(
                "# Current: "
                + json.dumps(
                    redactor.record(record_dict(dict(decision.current))), ensure_ascii=True
                )
            )
        if decision.target is not None:
            lines.append(f"fingerprint = {json.dumps(require_target(decision.target).fingerprint)}")
        answer = answered.get((kind.id, decision.target.path if decision.target else None))
        lines.extend(_answer_lines(kind, answer))
        lines.append("")
    lines.extend(_not_carried_lines(not_carried, redactor))
    if fidelity is not None:
        lines += [
            "[fidelity]",
            *[key + " = " + json.dumps(value) for key, value in record_dict(fidelity).items()],
            "",
        ]
    return "\n".join(lines)


def _not_carried_lines(
    not_carried: Iterable[tuple[Decision, str]], redactor: Redactor
) -> list[str]:
    lines: list[str] = []
    for answer, reason in not_carried:
        key = "decisions." + json.dumps(answer.kind.id)
        if answer.target is not None:
            key += "." + json.dumps(answer.target.path)
        lines += [
            "# Not carried: " + json.dumps(redactor.text(reason), ensure_ascii=True),
            "# [" + key + "]",
        ]
        if answer.target is not None:
            lines.append("# fingerprint = " + json.dumps(answer.target.fingerprint))
        lines.extend("# " + line for line in _answer_lines(answer.kind, answer))
        lines.append("")
    return lines


def _answer_lines(kind: DecisionKind, answer: Decision | None) -> list[str]:
    if answer is not None:
        return [
            key + " = " + json.dumps(value, ensure_ascii=True)
            for key, value in record_dict(answer.answer).items()
            if value is not None
        ]
    lines = []
    hints = get_type_hints(kind.answer_type, include_extras=True)
    for field in fields_of(kind.answer_type):
        help_text = schema_for(hints[field.name], input=True).get("description", field.name)
        placeholder = _placeholder(field, hints[field.name])
        lines.append(
            f"# {field.name} = {json.dumps(placeholder, ensure_ascii=True)}  # {help_text}"
        )
    return lines


def _finding_comments(
    decision: OpenDecision, findings: tuple[Finding, ...], redactor: Redactor
) -> list[str]:
    lines: list[str] = []
    for rule in decision.rules:
        related = [
            finding
            for finding in findings
            if finding.rule is rule
            and (
                decision.target is None
                or (finding.location is not None and finding.location.path == decision.target.path)
            )
        ]
        if related:
            for finding in related:
                lines.append(
                    f"# {rule.id} {finding.severity.value}: "
                    + json.dumps(redactor.text(finding.message), ensure_ascii=True)
                )
                if finding.details:
                    lines.append(
                        "# Detail: "
                        + json.dumps(redactor.record(dict(finding.details)), ensure_ascii=True)
                    )
        else:
            lines.append(f"# {rule.id} {rule.severity.value}: {rule.title}")
    return lines


def _context_comment(context: QuestionContext, redactor: Redactor) -> str:
    parts = [context.element_kind]
    for value in (context.name, context.excerpt):
        if value:
            parts.append(json.dumps(redactor.text(value)[:60], ensure_ascii=True))
    for label, value in (
        ("page", context.page),
        ("sheet", context.sheet),
        ("slide", context.slide),
    ):
        if value:
            parts.append(label + " " + json.dumps(redactor.text(value)[:60], ensure_ascii=True))
    return "# " + ", ".join(parts)


def _placeholder(field: dataclasses.Field[object], value_type: object) -> object:
    schema = schema_for(value_type, input=True)
    if "minimum" in schema:
        return schema["minimum"]
    if value_type is bool:
        return True
    if field.default is not dataclasses.MISSING and field.default is not None:
        return field.default
    # Optional strings and booleans get explicit placeholders, never inferred meaning.
    return True if "bool" in str(value_type) else [] if "tuple" in str(value_type) else ""


def answer_schema(answer_type: type[object]) -> JsonObject:
    """Derive the sparse input schema from answer fields, defaults and constraints.

    Returns
    -------
    JsonObject
        Strict answer properties, with cross-field requirements from the answer class.

    """
    return schema_for(answer_type, input=True)


def plan_schema(kinds: Mapping[str, DecisionKind]) -> JsonObject:
    """Describe the plan file using its generated, annotated table contract."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:odfa11y:schema:plan-file",
        **schema_for(file_contract(kinds), input=True),
    }


def decision_schema(kinds: Mapping[str, DecisionKind], *, open_decision: bool) -> JsonObject:
    """Describe kind-dependent decision projections from their annotations."""
    return schema_for(decision_contract(kinds, open_decision=open_decision))


def decision_reference(kinds: Mapping[str, DecisionKind]) -> str:
    """Describe registered answers from the same schema used by the parser.

    Returns
    -------
    str
        A Markdown reference fragment with authoritative answer fields and constraints.

    """
    lines = ["## Registered decisions", ""]
    for kind in kinds.values():
        lines += [f"### `{kind.id}`", "", f"Scope: {kind.scope.value}.", ""]
        if kind.scope == DecisionScope.TARGET:
            lines += ["Use the audit's canonical target and mandatory fingerprint.", ""]
        schema = answer_schema(kind.answer_type)
        required = cast("list[str]", schema.get("required", []))
        lines += ["| Field | Required | Value constraints | Help |", "| --- | --- | --- | --- |"]
        properties = cast("dict[str, JsonObject]", schema["properties"])
        for name, field_schema in properties.items():
            constraints = {
                key: value for key, value in field_schema.items() if key != "description"
            }
            value = json.dumps(constraints, ensure_ascii=False, separators=(",", ":"))
            help_text = str(field_schema.get("description", "")).replace("|", "\\|")
            lines.append(
                f"| `{name}` | {'yes' if name in required else 'no'} | `{value}` | {help_text} |"
            )
        if alternatives := schema.get("anyOf"):
            lines += ["", "Required-field alternatives: `" + json.dumps(alternatives) + "`."]
        lines.append("")

    return "\n".join(lines)
