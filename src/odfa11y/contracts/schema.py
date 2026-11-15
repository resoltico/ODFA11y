# SPDX-License-Identifier: MPL-2.0
"""Derive JSON Schema from runtime-visible contract annotations."""

import dataclasses
import enum
import types
from collections.abc import Mapping
from pathlib import Path
from typing import (
    Any,
    ClassVar,
    Literal,
    TypedDict,
    Union,
    cast,
    get_args,
    get_origin,
    is_typeddict,
)

from odfa11y.contracts.constraints import Constraint, Description
from odfa11y.contracts.decode import encode
from odfa11y.contracts.types import (
    JsonObject,
    JsonValue,
    computed_hints,
    fields_of,
    record_hints,
    root_contract,
    split,
)


def mapping_contract(name: str, fields: Mapping[str, object], *, total: bool = True) -> object:
    """Create an annotated mapping for a producer-owned dynamic catalogue."""
    # Runtime TypedDict supports mappings; static checkers can only infer literal keys.
    return TypedDict(name, dict(fields), total=total)  # ty: ignore[invalid-argument-type]


@dataclasses.dataclass(frozen=True, slots=True)
class _Schema:
    input: bool
    overrides: Mapping[object, object]

    def value(self, annotation: object) -> JsonObject:
        if annotation in self.overrides:
            return self.value(self.overrides[annotation])
        if annotation in (object, Any, JsonValue):
            return {}
        if annotation is JsonObject:
            return {"type": "object"}
        base, constraints = split(annotation)
        result = self.typed(base)
        for constraint in constraints:
            if isinstance(constraint, Description):
                result.update(cast("JsonObject", constraint.schema()))
            else:
                result = _constrain_nullable(result, constraint)
        return result

    def typed(self, annotation: object) -> JsonObject:
        scalar: dict[object, str] = {
            type(None): "null",
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            Path: "string",
        }
        if annotation in scalar:
            return {"type": scalar[annotation]}
        origin, args = get_origin(annotation), get_args(annotation)
        if origin in (types.UnionType, Union):
            return {"anyOf": [self.value(arg) for arg in args]}
        if origin is Literal:
            return {"enum": [encode(arg) for arg in args]}
        if origin in (tuple, list):
            return self.sequence(origin, args)
        if origin in (dict, Mapping):
            return self.mapping(args)
        if is_typeddict(annotation):
            return self.typed_mapping(annotation)
        return self.record(annotation)

    def sequence(self, origin: object, args: tuple[object, ...]) -> JsonObject:
        if origin is tuple and len(args) > 1 and args[-1] is not Ellipsis:
            return {
                "type": "array",
                "prefixItems": [self.value(arg) for arg in args],
                "minItems": len(args),
                "maxItems": len(args),
                "items": False,
            }
        return {"type": "array", "items": self.value(args[0]) if args else {}}

    def mapping(self, args: tuple[object, ...]) -> JsonObject:
        key, value = args if args else (str, object)
        result: JsonObject = {"type": "object", "additionalProperties": self.value(value)}
        if key is not str:
            result["propertyNames"] = self.value(key)
        return result

    def typed_mapping(self, annotation: object) -> JsonObject:
        return {
            "type": "object",
            "properties": {
                name: self.value(hint) for name, hint in record_hints(annotation).items()
            },
            "required": cast(list[JsonValue], sorted(getattr(annotation, "__required_keys__", ()))),
            "additionalProperties": False,
        }

    def record(self, annotation: object) -> JsonObject:
        concrete = get_origin(annotation) or annotation
        if isinstance(concrete, type) and issubclass(concrete, enum.Enum):
            return {"enum": [encode(member.value) for member in concrete]}
        if not isinstance(concrete, type):
            message = f"Unsupported contract annotation: {annotation}"
            raise TypeError(message)
        if not dataclasses.is_dataclass(concrete):
            root = root_contract(concrete)
            if root is not None:
                return self.value(root)
            message = f"Unsupported contract class: {concrete.__name__}"
            raise TypeError(message)
        return self.dataclass(annotation)

    def dataclass(self, annotation: object) -> JsonObject:
        hints = record_hints(annotation)
        properties: JsonObject = {}
        required: list[JsonValue] = []
        for field in fields_of(get_origin(annotation) or annotation):
            if field.name.startswith("_"):
                continue
            properties[field.name] = self.value(hints[field.name])
            if not self.input or (
                field.default is dataclasses.MISSING
                and field.default_factory is dataclasses.MISSING
            ):
                required.append(field.name)
        if not self.input:
            for name, hint in computed_hints(annotation).items():
                properties[name] = self.value(hint)
                required.append(name)
        result: JsonObject = {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }
        whole = hints.get("__contract__")
        if get_origin(whole) is ClassVar:
            _base, constraints = split(get_args(whole)[0])
            for constraint in constraints:
                result = _merge(result, cast("JsonObject", constraint.schema()))
        return result


def _merge(base: JsonObject, fragment: JsonObject) -> JsonObject:
    if base.keys() & fragment.keys():
        return {**base, "allOf": [*cast(list[JsonValue], base.get("allOf", [])), fragment]}
    return base | fragment


def _constrain_nullable(base: JsonObject, constraint: Constraint) -> JsonObject:
    fragment = cast("JsonObject", constraint.schema())
    alternatives = base.get("anyOf")
    if isinstance(alternatives, list):
        return {
            **base,
            "anyOf": [
                item
                if isinstance(item, dict) and item.get("type") == "null"
                else _merge(cast("JsonObject", item), fragment)
                for item in alternatives
            ],
        }
    return _merge(base, fragment)


def schema_for(
    annotation: object, *, input: bool = False, overrides: Mapping[object, object] | None = None
) -> JsonObject:
    """Describe a contract using the same typed constraints as decoding and encoding."""
    return _Schema(input, overrides or {}).value(annotation)
