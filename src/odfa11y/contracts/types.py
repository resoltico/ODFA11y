# SPDX-License-Identifier: MPL-2.0
"""Runtime annotation inspection shared by all contract operations."""

import dataclasses
import types
from collections.abc import Callable, Mapping
from functools import reduce
from operator import or_
from typing import (
    Annotated,
    Any,
    ClassVar,
    Literal,
    NotRequired,
    Required,
    TypeAliasType,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
    is_typeddict,
)

from odfa11y.contracts.constraints import Constraint, Description

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None
type JsonObject = dict[str, JsonValue]


class JsonProperty(property):
    """An annotated computed field in a published record."""


def split(annotation: object) -> tuple[object, tuple[Constraint | Description, ...]]:
    if isinstance(annotation, TypeAliasType):
        return split(annotation.__value__)
    if get_origin(annotation) in (Required, NotRequired):
        return split(get_args(annotation)[0])
    if get_origin(annotation) is Annotated:
        base, *metadata = get_args(annotation)
        return base, tuple(item for item in metadata if isinstance(item, (Constraint, Description)))
    return annotation, ()


def root_contract(value_type: type[object]) -> object | None:
    annotation = get_type_hints(value_type, include_extras=True).get("__contract__")
    return get_args(annotation)[0] if get_origin(annotation) is ClassVar else None


def fields_of(value: object) -> tuple[dataclasses.Field[Any], ...]:
    if not dataclasses.is_dataclass(value):
        message = "A record contract requires a dataclass"
        raise TypeError(message)
    fields = dataclasses.fields(value)
    if any(field.metadata for field in fields):
        message = "Contract fields use Annotated constraints, not field metadata"
        raise TypeError(message)
    return fields


def record_hints(value_type: object) -> dict[str, object]:
    origin = get_origin(value_type) or value_type
    if not isinstance(origin, type):
        message = f"Not a record type: {value_type}"
        raise TypeError(message)
    parameters = cast(tuple[object, ...], getattr(origin, "__type_params__", ()))
    bindings: dict[object, object] = dict(zip(parameters, get_args(value_type), strict=False))
    return {
        name: bind(annotation, bindings)
        for name, annotation in get_type_hints(origin, include_extras=True).items()
    }


def bind(annotation: object, bindings: Mapping[object, object]) -> object:
    if isinstance(annotation, TypeVar):
        return bindings.get(annotation, object)
    origin, args = get_origin(annotation), get_args(annotation)
    if not origin or not args or origin is Literal:
        return annotation
    values = tuple(bind(value, bindings) for value in args)
    if origin in (types.UnionType, Union):
        return reduce(or_, values)
    if origin is Annotated:
        return Annotated[values]
    return origin[values[0]] if len(values) == 1 else origin[values]


def computed_hints(value_type: object) -> dict[str, object]:
    origin = get_origin(value_type) or value_type
    if not isinstance(origin, type):
        return {}
    bindings: dict[object, object] = dict(
        zip(
            cast(tuple[object, ...], getattr(origin, "__type_params__", ())),
            get_args(value_type),
            strict=False,
        )
    )
    return {
        name: bind(get_type_hints(descriptor.fget, include_extras=True)["return"], bindings)
        for parent in reversed(origin.__mro__)
        for name, descriptor in vars(parent).items()
        if isinstance(descriptor, JsonProperty) and descriptor.fget is not None
    }


def format_validators(annotations: tuple[object, ...]) -> dict[str, object]:
    """Collect scalar format checks from the annotations actually in use."""
    pending = list(annotations)
    seen = set()
    formats: dict[str, Constraint] = {}
    while pending:
        annotation = pending.pop()
        if annotation in seen:
            continue
        seen.add(annotation)
        if isinstance(annotation, TypeAliasType):
            pending.append(annotation.__value__)
            continue
        base, metadata = split(annotation)
        for constraint in metadata:
            name = getattr(constraint, "format_name", None)
            if name is not None and isinstance(constraint, Constraint):
                if name in formats and formats[name] != constraint:
                    message = f"Conflicting scalar format {name}"
                    raise TypeError(message)
                formats[name] = constraint
        pending.extend(_annotation_children(base))
    return {name: _format_check(constraint) for name, constraint in formats.items()}


def _annotation_children(annotation: object) -> tuple[object, ...]:
    origin = get_origin(annotation)
    children = (
        []
        if origin is Literal
        else [value for value in get_args(annotation) if value is not Ellipsis]
    )
    concrete = origin or annotation
    if isinstance(concrete, type) and (
        dataclasses.is_dataclass(concrete) or is_typeddict(concrete)
    ):
        children.extend(record_hints(annotation).values())
    elif isinstance(concrete, type):
        root = root_contract(concrete)
        if root is not None:
            children.append(root)
    return tuple(children)


def _format_check(constraint: Constraint) -> Callable[[object], bool]:
    return lambda value: not constraint.problems(value)
