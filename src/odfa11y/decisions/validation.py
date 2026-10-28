# SPDX-License-Identifier: MPL-2.0
"""Validate registered answer dataclasses without coercing unsupported input types."""

from __future__ import annotations

import dataclasses
import enum
import math
import re
import types
from typing import TYPE_CHECKING, Literal, cast, get_args, get_origin, get_type_hints

from odfa11y.errors import PlanError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from _typeshed import DataclassInstance


def decode_answer[T](answer_type: type[T], values: Mapping[str, object], label: str) -> T:
    """Validate a table against the declared fields, defaults and constraints.

    Returns
    -------
    T
        The registered answer value.

    Invalid keys, types and constraints raise PlanError from field validation.

    """
    return answer_type(**_validated_arguments(answer_type, values, label))


def validate_answer(answer: object, label: str) -> None:
    """Apply the same field contract to answers constructed by Python callers."""
    _validated_arguments(
        type(answer),
        {
            field.name: getattr(answer, field.name)
            for field in dataclasses.fields(cast("DataclassInstance", answer))
        },
        label,
    )


def _validated_arguments(
    answer_type: type[object], values: Mapping[str, object], label: str
) -> dict[str, object]:
    if not all(isinstance(key, str) for key in values):
        msg = f"{label} requires string field names"
        raise PlanError(msg)
    fields = dataclasses.fields(cast("type[DataclassInstance]", answer_type))
    unknown = values.keys() - {field.name for field in fields}
    if unknown:
        msg = f"Unknown {label} keys: {', '.join(sorted(unknown))}"
        raise PlanError(msg)
    hints = get_type_hints(answer_type)
    arguments = {}
    for field in fields:
        value = _field_value(field, values, label)
        try:
            value = _typed(value, hints[field.name], f"{label}.{field.name}")
            _constraints(value, field.metadata.get("schema", {}), f"{label}.{field.name}")
            validator = field.metadata.get("validate")
            if validator is not None and value is not None:
                validator(value)
        except (ValueError, PlanError) as exc:
            if error := field.metadata.get("error"):
                msg = f"{label}.{field.name} {error}"
                raise PlanError(msg) from exc
            if isinstance(exc, PlanError):
                raise
            msg = f"{label}.{field.name}: {exc}"
            raise PlanError(msg) from exc
        arguments[field.name] = value
    required_any = getattr(answer_type, "required_any", ())
    if required_any and not any(arguments[name] is not None for name in required_any):
        msg = f"{label} requires at least one of {', '.join(required_any)}"
        raise PlanError(msg)
    return arguments


def _field_value(
    field: dataclasses.Field[object], values: Mapping[str, object], label: str
) -> object:
    if field.name in values:
        return values[field.name]
    if field.default is not dataclasses.MISSING:
        return field.default
    if field.default_factory is not dataclasses.MISSING:
        return field.default_factory()
    msg = f"{label}.{field.name} is required"
    raise PlanError(msg)


def _typed(value: object, expected: object, label: str) -> object:
    origin, arguments = get_origin(expected), get_args(expected)
    if origin is types.UnionType:
        return _union(value, arguments, label)
    if origin is Literal:
        if any(type(value) is type(item) and value == item for item in arguments):
            return value
    elif origin in {tuple, list}:
        if isinstance(value, (tuple, list)):
            items = [_typed(item, arguments[0], label) for item in value]
            return tuple(items) if origin is tuple else items
    elif dataclasses.is_dataclass(expected) and isinstance(expected, type):
        return _record_value(value, expected, label)
    elif isinstance(expected, type) and issubclass(expected, enum.Enum):
        return _enum_value(value, expected, label)
    elif _scalar_matches(value, expected):
        return float(cast("float", value)) if expected is float else value
    msg = f"{label} must satisfy {expected}"
    raise PlanError(msg)


def _union(value: object, choices: tuple[object, ...], label: str) -> object:
    for choice in choices:
        try:
            return _typed(value, choice, label)
        except PlanError:
            continue
    msg = f"{label} has an unsupported value type"
    raise PlanError(msg)


def _record_value(value: object, expected: type[object], label: str) -> object:
    if isinstance(value, dict):
        return decode_answer(expected, value, label)
    if type(value) is expected:
        validate_answer(value, label)
        return value
    msg = f"{label} requires a {expected.__name__} table"
    raise PlanError(msg)


def _enum_value(value: object, expected: type[enum.Enum], label: str) -> enum.Enum:
    if type(value) is expected:
        return value
    if any(type(value) is type(member.value) and value == member.value for member in expected):
        return expected(value)
    msg = f"{label} has an unsupported choice"
    raise PlanError(msg)


def _scalar_matches(value: object, expected: object) -> bool:
    if expected is type(None):
        return value is None
    if expected is float:
        try:
            return type(value) in {int, float} and math.isfinite(cast("float", value))
        except OverflowError:
            return False
    if expected in {str, int, bool}:
        return type(value) is expected
    return False


def _constraints(value: object, schema: Mapping[str, object], label: str) -> None:
    if value is None:
        return
    if isinstance(value, str):
        _string_constraints(value, schema, label)
    elif isinstance(value, (tuple, list)):
        if len(value) < cast("int", schema.get("minItems", 0)):
            msg = f"{label} has too few items"
            raise PlanError(msg)
        for item in value:
            _constraints(item, cast("Mapping[str, object]", schema.get("items", {})), label)
    elif type(value) in {int, float}:
        _number_constraints(cast("float", value), schema, label)
    if "enum" in schema and value not in cast("list[object]", schema["enum"]):
        msg = f"{label} must be one of {schema['enum']}"
        raise PlanError(msg)


def _string_constraints(value: str, schema: Mapping[str, object], label: str) -> None:
    if len(value) < cast("int", schema.get("minLength", 0)):
        msg = f"{label} is too short"
        raise PlanError(msg)
    if "pattern" in schema and re.search(cast("str", schema["pattern"]), value) is None:
        msg = f"{label} does not match its required syntax"
        raise PlanError(msg)


def _number_constraints(value: float, schema: Mapping[str, object], label: str) -> None:
    if ("minimum" in schema and value < cast("float", schema["minimum"])) or (
        "maximum" in schema and value > cast("float", schema["maximum"])
    ):
        msg = f"{label} is outside its supported range"
        raise PlanError(msg)
