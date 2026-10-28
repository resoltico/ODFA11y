# SPDX-License-Identifier: MPL-2.0
"""One strict plan codec derives parsing, templates and schema from registered answers."""

from __future__ import annotations

import dataclasses
import json
import sys
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, cast, get_type_hints

from odfa11y.decisions import (
    TARGET_FINGERPRINT_PATTERN,
    TARGET_PATH_PATTERN,
    Decision,
    DecisionScope,
    decode_answer,
)
from odfa11y.errors import PlanError
from odfa11y.fidelity import FidelityPolicy
from odfa11y.report import Location
from odfa11y.serialization import record_dict, schema_for

from .models import PLAN_FORMAT, Plan, PlanHeader

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from _typeshed import DataclassInstance

    from odfa11y.decisions import DecisionKind, OpenDecision
    from odfa11y.serialization import JsonObject, JsonValue


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
    unknown = values.keys() - {"plan", "decisions", "fidelity"}
    if unknown:
        msg = f"Unknown plan tables: {', '.join(sorted(unknown))}"
        raise PlanError(msg)
    if "plan" not in values:
        msg = "A [plan] source-binding header is required"
        raise PlanError(msg)
    header = decode_answer(PlanHeader, _table(values["plan"], "plan"), "plan")
    answers = []
    for kind_id, value in _table(values.get("decisions", {}), "decisions").items():
        if kind_id not in kinds:
            msg = f"Unknown decision kind: {kind_id}"
            raise PlanError(msg)
        kind = kinds[kind_id]
        table = _table(value, kind_id)
        if kind.scope == DecisionScope.DOCUMENT:
            answers.append(_answer(kind, None, table))
        else:
            answers.extend(
                _answer(kind, Location(target), _table(raw, target))
                for target, raw in table.items()
            )
    fidelity = decode_answer(
        FidelityPolicy, _table(values.get("fidelity", {}), "fidelity"), "fidelity"
    )
    return Plan(header, tuple(answers), fidelity)


def _answer(kind: DecisionKind, target: Location | None, values: Mapping[str, object]) -> Decision:
    fields = dict(values)
    fingerprint = fields.pop("fingerprint", None) if target is not None else None
    if fingerprint is not None and not isinstance(fingerprint, str):
        msg = f"{kind.id}.fingerprint must be a string"
        raise PlanError(msg)
    answer = decode_answer(kind.answer_type, fields, kind.id)
    return Decision(kind, target, fingerprint, answer)


def _table(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        msg = f"{label} must be a table with string keys"
        raise PlanError(msg)
    return value


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
        f"format = {PLAN_FORMAT}",
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
        if decision.fingerprint is not None:
            lines.append(f"# fingerprint = {json.dumps(decision.fingerprint)}")
        hints = get_type_hints(kind.answer_type)
        for field in dataclasses.fields(cast("type[DataclassInstance]", kind.answer_type)):
            help_text = field.metadata.get("schema", {}).get("description", field.name)
            placeholder = _placeholder(field, hints[field.name])
            lines.append(
                f"# {field.name} = {json.dumps(placeholder, ensure_ascii=False)}  # {help_text}"
            )
        lines.append("")
    return "\n".join(lines)


def _placeholder(field: dataclasses.Field[object], value_type: object) -> object:
    schema = field.metadata.get("schema", {})
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
    hints = get_type_hints(answer_type)
    fields = dataclasses.fields(cast("type[DataclassInstance]", answer_type))
    properties: JsonObject = {
        field.name: schema_for(
            hints[field.name], namespace=vars(sys.modules[answer_type.__module__])
        )
        | field.metadata.get("schema", {})
        for field in fields
    }
    required: list[JsonValue] = [
        field.name
        for field in fields
        if field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING
    ]
    result: JsonObject = {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
    required_any = getattr(answer_type, "required_any", ())
    if required_any:
        result["anyOf"] = [
            {"required": [name], "properties": {name: {"not": {"type": "null"}}}}
            for name in required_any
        ]
    return result


def plan_schema(kinds: Mapping[str, DecisionKind]) -> JsonObject:
    """Derive the complete plan-file schema from registered kinds.

    Returns
    -------
    JsonObject
        The strict binding envelope and document/target answer tables.

    """
    properties: JsonObject = {}
    for kind in kinds.values():
        body = answer_schema(kind.answer_type)
        if kind.scope == DecisionScope.DOCUMENT:
            properties[kind.id] = body
        else:
            answer_properties = cast("JsonObject", body["properties"])
            answer_properties["fingerprint"] = {
                "type": "string",
                "pattern": "^" + TARGET_FINGERPRINT_PATTERN + r"(?![\s\S])",
            }
            required = cast("list[JsonValue]", body["required"])
            required.append("fingerprint")
            properties[kind.id] = {
                "type": "object",
                "propertyNames": {"pattern": TARGET_PATH_PATTERN},
                "additionalProperties": body,
            }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:odfa11y:schema:plan",
        "type": "object",
        "properties": {
            "plan": schema_for(PlanHeader, namespace=globals()),
            "decisions": {
                "type": "object",
                "properties": properties,
                "additionalProperties": False,
            },
            "fidelity": answer_schema(FidelityPolicy),
        },
        "required": ["plan"],
        "additionalProperties": False,
    }


def decision_schema(kinds: Mapping[str, DecisionKind], *, open_decision: bool) -> JsonObject:
    """Describe a decision record with the exact kind-dependent target and answer contract.

    Returns
    -------
    JsonObject
        One registered variant per decision kind.

    """
    variants: list[JsonValue] = []
    for kind in kinds.values():
        targeted = kind.scope == DecisionScope.TARGET
        properties: JsonObject = {
            "kind": {"const": kind.id},
            "target": schema_for(Location, namespace=globals()) if targeted else {"type": "null"},
            "fingerprint": {
                "type": "string",
                "pattern": "^" + TARGET_FINGERPRINT_PATTERN + r"(?![\s\S])",
            }
            if targeted
            else {"type": "null"},
        }
        if open_decision:
            properties |= {
                "current": {"type": "object"},
                "rule_ids": {"type": "array", "items": {"type": "string"}},
            }
        else:
            properties["answer"] = schema_for(
                kind.answer_type, namespace=vars(sys.modules[kind.answer_type.__module__])
            )
        variants.append({
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        })
    return {"oneOf": variants}


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
        lines += ["```json", json.dumps(schema, indent=2, ensure_ascii=False), "```", ""]
    return "\n".join(lines)
