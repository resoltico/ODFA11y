# SPDX-License-Identifier: MPL-2.0
"""Serialize typed records and derive their published JSON schemas."""

from __future__ import annotations

import dataclasses
import enum
import math
import sys
import types
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, cast, get_args, get_origin, get_type_hints

from odfa11y.errors import ReportError

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None
type JsonObject = dict[str, JsonValue]


class JsonProperty(property):
    """A computed, typed field included in serialization and schema generation."""


class DictionaryRecord(Protocol):
    """A value that supplies a JSON-compatible dictionary."""

    def as_dict(self) -> dict[str, object]:
        """Describe the record.

        Returns
        -------
        dict[str, object]
            Its serialized fields.

        """
        ...


def encode(value: object) -> JsonValue:
    """Convert typed records, collections, paths and enums into JSON values.

    Returns
    -------
    JsonValue
        A JSON-compatible projection, honoring field serialization metadata.

    Raises
    ------
    ReportError
        An unsupported value cannot be published as JSON.

    """
    if isinstance(value, float) and not math.isfinite(value):
        msg = "Non-finite values cannot be published as JSON."
        raise ReportError(msg)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, enum.Enum):
        return encode(value.value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _dataclass_dict(value)
    if callable(getattr(value, "as_dict", None)):
        return encode(cast("DictionaryRecord", value).as_dict())
    msg = f"Unsupported JSON value: {type(value).__name__}"
    raise ReportError(msg)


def _dataclass_dict(value: DataclassInstance) -> JsonObject:
    result: JsonObject = {}
    for field in dataclasses.fields(value):
        if field.metadata.get("serialize", True):
            item = getattr(value, field.name)
            if field.metadata.get("basename") and item is not None:
                item = item.name
            if attribute := field.metadata.get("attribute"):
                item = getattr(item, attribute)
            result[field.metadata.get("json_name", field.name)] = encode(item)
    for name, descriptor in vars(type(value)).items():
        if isinstance(descriptor, JsonProperty):
            result[name] = encode(getattr(value, name))
    return result


def record_dict(value: object) -> JsonObject:
    """Serialize a record whose published top-level shape is an object.

    Returns
    -------
    JsonObject
        The record's fields.

    Raises
    ------
    ReportError
        The value does not describe an object.

    """
    result = encode(value)
    if not isinstance(result, dict):
        msg = "A published record must be a JSON object."
        raise ReportError(msg)
    return result


def schema_for(
    value_type: object,
    *,
    namespace: Mapping[str, object],
    overrides: Mapping[object, JsonObject] | None = None,
) -> JsonObject:
    """Derive a Draft 2020-12 fragment from record annotations and serialized properties.

    Returns
    -------
    JsonObject
        A schema with strict dataclass properties and recursively typed collections.

    Unsupported annotations raise ReportError from the class/type dispatcher.

    """
    overrides = overrides or {}
    if value_type in overrides:
        return overrides[value_type]
    if value_type is object or value_type in {JsonValue, JsonObject}:
        return {} if value_type is not JsonObject else {"type": "object"}
    scalars: dict[object, str] = {
        type(None): "null",
        str: "string",
        Path: "string",
        bool: "boolean",
        int: "integer",
        float: "number",
    }
    if kind := scalars.get(value_type):
        return {"type": kind}
    origin, arguments = get_origin(value_type), get_args(value_type)

    def recurse(item: object) -> JsonObject:
        return schema_for(item, namespace=namespace, overrides=overrides)

    if origin is types.UnionType:
        return {"anyOf": [recurse(item) for item in arguments]}
    if origin is Literal:
        return {"enum": [encode(item) for item in arguments]}
    if origin in {list, tuple}:
        return {"type": "array", "items": recurse(arguments[0])}
    if origin in {dict, Mapping}:
        return {"type": "object", "additionalProperties": recurse(arguments[1])}
    return _class_schema(value_type, namespace, overrides)


def _class_schema(
    value_type: object, namespace: Mapping[str, object], overrides: Mapping[object, JsonObject]
) -> JsonObject:
    if isinstance(value_type, type) and issubclass(value_type, enum.Enum):
        return {"enum": [encode(item.value) for item in value_type]}
    if not dataclasses.is_dataclass(value_type) or not isinstance(value_type, type):
        msg = f"Unsupported JSON schema annotation: {value_type}"
        raise ReportError(msg)
    globalns = vars(sys.modules[value_type.__module__]) | dict(namespace)
    hints = get_type_hints(value_type, globalns=globalns)
    properties: JsonObject = {
        field.metadata.get("json_name", field.name): schema_for(
            hints[field.name], namespace=namespace, overrides=overrides
        )
        | field.metadata.get("schema", {})
        for field in dataclasses.fields(value_type)
        if field.metadata.get("serialize", True)
    }
    for name, descriptor in vars(value_type).items():
        if isinstance(descriptor, JsonProperty) and descriptor.fget is not None:
            properties[name] = schema_for(
                get_type_hints(descriptor.fget, globalns=globalns)["return"],
                namespace=namespace,
                overrides=overrides,
            )
    required: list[JsonValue] = [*properties]
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
