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
from odfa11y.errors import PlanError
from odfa11y.plans.contracts import PlanFile, decision_contract, file_contract, from_file
from odfa11y.plans.model import PLAN_SCHEMA_VERSION, Plan, PlanHeader
from odfa11y.targets import (
    require_target,
)
lazy from odfa11y.contracts import JsonObject
lazy from odfa11y.decisions import DecisionKind, OpenDecision


def parse_plan(path: str | Path, kinds: Mapping[str, DecisionKind]) -> Plan:
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
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        msg = f"Cannot read plan: {exc}"
        raise PlanError(msg) from exc
    return parse_tables(values, kinds)


def parse_tables(values: Mapping[str, object], kinds: Mapping[str, DecisionKind]) -> Plan:
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
    record = cast(
        PlanFile[Mapping[str, object]], decode(contract, values, label="plan", error=PlanError)
    )
    return from_file(record, kinds)


def render_plan(header: PlanHeader, decisions: Iterable[OpenDecision]) -> str:
    """Print the binding header and disabled, reviewable answers with shared field help.

    Returns
    -------
    str
        TOML with active binding metadata and commented decision tables.

    """
    lines = [
        "# Review each answer before enabling it; this file does not change a source by itself.",
        "[plan]",
        f"schema_version = {PLAN_SCHEMA_VERSION}",
        f"generator = {json.dumps(header.generator)}",
        f"source.sha256 = {json.dumps(header.source.sha256)}",
        "",
    ]
    for decision in decisions:
        kind = decision.kind
        key = "decisions." + json.dumps(kind.id)
        if decision.target is not None:
            key += "." + json.dumps(decision.target.path)
        lines += [f"# [{key}]", f"# Rules: {', '.join(decision.rule_ids)}"]
        if decision.current:
            lines.append(
                "# Current: " + json.dumps(record_dict(dict(decision.current)), ensure_ascii=False)
            )
        if decision.target is not None:
            lines.append(
                f"# fingerprint = {json.dumps(require_target(decision.target).fingerprint)}"
            )
        hints = get_type_hints(kind.answer_type, include_extras=True)
        for field in fields_of(kind.answer_type):
            help_text = schema_for(hints[field.name], input=True).get("description", field.name)
            placeholder = _placeholder(field, hints[field.name])
            lines.append(
                f"# {field.name} = {json.dumps(placeholder, ensure_ascii=False)}  # {help_text}"
            )
        lines.append("")
    return "\n".join(lines)


def _placeholder(field: dataclasses.Field[object], value_type: object) -> object:
    schema = schema_for(value_type, input=True)
    if "minimum" in schema:
        return schema["minimum"]
    if value_type is bool:
        return False
    if field.default is not dataclasses.MISSING and field.default is not None:
        return field.default
    # Optional strings and booleans get explicit placeholders, never inferred meaning.
    return False if "bool" in str(value_type) else [] if "tuple" in str(value_type) else ""


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
