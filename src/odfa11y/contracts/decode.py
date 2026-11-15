# SPDX-License-Identifier: MPL-2.0
"""Walk declared contracts for strict decoding, validation and encoding."""

import dataclasses
import enum
import math
import types
from collections.abc import Mapping
from pathlib import Path
from typing import (
    Any,
    ClassVar,
    Literal,
    Protocol,
    Union,
    cast,
    get_args,
    get_origin,
    is_typeddict,
    overload,
)

from odfa11y.contracts.constraints import Constraint
from odfa11y.contracts.types import (
    JsonObject,
    JsonValue,
    computed_hints,
    fields_of,
    record_hints,
    root_contract,
    split,
)
from odfa11y.errors import InvalidOption, OdfA11yError


class RootProjection(Protocol):
    def as_dict(self) -> object: ...


_INVALID = object()
type Mode = Literal["decode", "validate", "encode"]


@dataclasses.dataclass(slots=True)
class _Walker:
    mode: Mode
    problems: list[str] = dataclasses.field(default_factory=list)

    def fail(self, path: str, reason: str) -> object:
        self.problems.append(f"{path}: {reason}")
        return _INVALID

    def value(self, value: object, annotation: object, path: str) -> object:
        if annotation in (object, Any, JsonValue, JsonObject):
            return self.free(value, path)
        base, constraints = split(annotation)
        result = (
            self.free(value, path)
            if base in (object, Any, JsonValue, JsonObject)
            else self.typed(value, base, path)
        )
        if result is not _INVALID:
            for constraint in constraints:
                if not isinstance(constraint, Constraint):
                    continue
                self.problems.extend(f"{path}: {reason}" for reason in constraint.problems(value))
        return result

    def typed(self, value: object, expected: object, path: str) -> object:
        origin, args = get_origin(expected), get_args(expected)
        if origin in (types.UnionType, Union):
            return self.union(value, args, path)
        if origin is Literal:
            return self.literal(value, args, path)
        if origin in (list, tuple) or expected in (list, tuple):
            return self.sequence(value, origin or expected, args, path)
        if origin in (dict, Mapping) or expected is dict:
            return self.mapping(value, args, path)
        if is_typeddict(expected):
            return self.typed_mapping(value, expected, path)
        concrete = origin or expected
        if isinstance(concrete, type) and dataclasses.is_dataclass(concrete):
            return self.record(value, expected, path)
        if isinstance(concrete, type) and issubclass(concrete, enum.Enum):
            return self.enumeration(value, concrete, path)
        return self.scalar(value, concrete, path)

    def union(self, value: object, choices: tuple[object, ...], path: str) -> object:
        choices = self.tagged_choices(value, choices, path)
        if not choices:
            return _INVALID
        failures = []
        for choice in choices:
            branch = _Walker(self.mode)
            result = branch.value(value, choice, path)
            if not branch.problems:
                return result
            failures.append(branch.problems)
        if failures:
            self.problems.extend(min(failures, key=len))
        else:
            self.fail(path, "has no accepted type")
        return _INVALID

    def tagged_choices(
        self, value: object, choices: tuple[object, ...], path: str
    ) -> tuple[object, ...]:
        if not isinstance(value, Mapping):
            return choices
        declarations = []
        for choice in choices:
            concrete = get_origin(choice) or choice
            if not isinstance(concrete, type) or not (
                dataclasses.is_dataclass(concrete) or is_typeddict(concrete)
            ):
                return choices
            declarations.append({
                name: get_args(split(hint)[0])
                for name, hint in record_hints(choice).items()
                if get_origin(split(hint)[0]) is Literal
            })
        common = (
            set.intersection(*(set(fields) for fields in declarations)) if declarations else set()
        )
        for name in sorted(common & value.keys()):
            matches = tuple(
                choice
                for choice, fields in zip(choices, declarations, strict=True)
                if _matches_literal(value[name], fields[name])
            )
            if len(matches) == 1:
                return matches
            if not matches:
                allowed = tuple(member for fields in declarations for member in fields[name])
                self.fail(f"{path}.{name}", f"must be one of {allowed}")
                return ()
        return choices

    def literal(self, value: object, choices: tuple[object, ...], path: str) -> object:
        scalar = value.value if isinstance(value, enum.Enum) else value
        for choice in choices:
            reference = choice.value if isinstance(choice, enum.Enum) else choice
            if type(scalar) is type(reference) and scalar == reference:
                return reference if self.mode == "encode" else choice
        return self.fail(path, f"must be one of {choices}")

    def sequence(
        self, value: object, origin: object, args: tuple[object, ...], path: str
    ) -> object:
        if not isinstance(value, list | tuple):
            return self.fail(path, "requires an array")
        fixed = origin is tuple and len(args) > 1 and args[-1] is not Ellipsis
        if fixed and len(value) != len(args):
            return self.fail(path, f"requires exactly {len(args)} items")
        result = [
            self.value(
                item, args[index] if fixed else args[0] if args else object, f"{path}[{index}]"
            )
            for index, item in enumerate(value)
        ]
        if self.mode == "encode" or origin is list:
            return result
        return tuple(result)

    def mapping(self, value: object, args: tuple[object, ...], path: str) -> object:
        if not isinstance(value, Mapping):
            return self.fail(path, "requires a table")
        key_type, value_type = args if args else (str, object)
        result = {}
        for key, item in value.items():
            converted = self.value(key, key_type, f"{path}.<key>")
            if self.mode == "encode" and not isinstance(converted, str):
                self.fail(path, "JSON object keys must be strings")
                continue
            if converted is not _INVALID:
                result[converted] = self.value(item, value_type, f"{path}.{key}")
        return result

    def typed_mapping(self, value: object, expected: object, path: str) -> object:
        if not isinstance(value, Mapping):
            return self.fail(path, "requires a table")
        hints = record_hints(expected)
        self.unknown(value, set(hints), path)
        required = getattr(expected, "__required_keys__", frozenset())
        for name in sorted(required - value.keys()):
            self.fail(f"{path}.{name}", "is required")
        return {
            name: self.value(value[name], hint, f"{path}.{name}")
            for name, hint in hints.items()
            if name in value
        }

    def record(self, value: object, expected: object, path: str) -> object:
        concrete = cast(type[Any], get_origin(expected) or expected)
        if self.mode == "decode" and isinstance(value, concrete):
            branch = _Walker("validate")
            result = branch.value(value, expected, path)
            self.problems.extend(branch.problems)
            return result
        if self.mode == "decode":
            if not isinstance(value, Mapping):
                return self.fail(path, f"requires a {concrete.__name__} table")
        elif not isinstance(value, concrete):
            return self.fail(path, f"requires {concrete.__name__}")
        hints = record_hints(expected)
        fields = [field for field in fields_of(concrete) if not field.name.startswith("_")]
        properties = computed_hints(expected) if self.mode != "decode" else {}
        names = {field.name for field in fields} | properties.keys()
        before = len(self.problems)
        if self.mode == "decode":
            self.unknown(cast("Mapping[object, object]", value), names, path)
        prepared = self.record_fields(value, fields, hints, path)
        for name, hint in properties.items():
            prepared[name] = self.value(getattr(value, name), hint, f"{path}.{name}")
        self.record_constraints(prepared, hints, path)
        if self.mode == "encode":
            return prepared
        if len(self.problems) != before:
            return _INVALID
        if self.mode == "validate":
            return value
        return self.materialize(concrete, fields, prepared, path)

    def materialize(
        self,
        concrete: type[Any],
        fields: list[dataclasses.Field[Any]],
        prepared: dict[str, object],
        path: str,
    ) -> object:
        arguments = {field.name: prepared[field.name] for field in fields if field.init}
        internal = [
            field
            for field in fields_of(concrete)
            if field.name.startswith("_")
            and field.init
            and field.default is dataclasses.MISSING
            and field.default_factory is dataclasses.MISSING
        ]
        if internal:
            return self.fail(
                path, f"{concrete.__name__} is a computed output contract, not a request"
            )
        return concrete(**arguments)

    def record_fields(
        self,
        value: object,
        fields: list[dataclasses.Field[Any]],
        hints: dict[str, object],
        path: str,
    ) -> dict[str, object]:
        prepared = {}
        for field in fields:
            if self.mode != "decode":
                item = getattr(value, field.name)
            elif field.name in cast("Mapping[str, object]", value):
                item = cast("Mapping[str, object]", value)[field.name]
            elif field.default is not dataclasses.MISSING:
                item = field.default
            elif field.default_factory is not dataclasses.MISSING:
                item = field.default_factory()
            else:
                self.fail(f"{path}.{field.name}", "is required")
                continue
            checked = self.value(item, hints[field.name], f"{path}.{field.name}")
            prepared[field.name] = item if checked is _INVALID else checked
        return prepared

    def record_constraints(
        self, prepared: dict[str, object], hints: dict[str, object], path: str
    ) -> None:
        annotation = hints.get("__contract__")
        if get_origin(annotation) is ClassVar:
            _base, constraints = split(get_args(annotation)[0])
            for constraint in constraints:
                if not isinstance(constraint, Constraint):
                    continue
                self.problems.extend(
                    f"{path}: {reason}" for reason in constraint.problems(prepared)
                )

    def enumeration(self, value: object, expected: type[enum.Enum], path: str) -> object:
        if type(value) is expected:
            return value.value if self.mode == "encode" else value
        if self.mode == "decode" and any(
            type(value) is type(member.value) and value == member.value for member in expected
        ):
            return expected(value)
        return self.fail(path, f"has an unsupported choice for {expected.__name__}")

    def scalar(self, value: object, expected: object, path: str) -> object:
        if expected is type(None):
            return None if value is None else self.fail(path, "requires null")
        if expected is float:
            if type(value) in (int, float) and (
                not isinstance(value, float) or math.isfinite(value)
            ):
                return value
            return self.fail(path, "requires a finite number")
        elif expected in (str, int, bool):
            if (expected is str and isinstance(value, str)) or type(value) is expected:
                return value
        elif expected is Path:
            if self.mode == "decode" and isinstance(value, str):
                return Path(value)
            if isinstance(value, Path):
                return str(value) if self.mode == "encode" else value
        elif isinstance(expected, type):
            return self.wrapper(value, expected, path)
        return self.fail(path, f"must satisfy {expected}")

    def wrapper(self, value: object, expected: type[object], path: str) -> object:
        contract = root_contract(expected)
        if contract is None:
            return self.fail(path, f"has an unsupported contract type {expected.__name__}")
        if self.mode == "decode":
            checked = self.value(value, contract, path)
            if checked is _INVALID:
                return checked
            if issubclass(expected, str) and isinstance(checked, str):
                try:
                    return expected(checked)
                except OdfA11yError as error:
                    return self.fail(path, str(error))
            return self.fail(path, f"{expected.__name__} is an output projection")
        if not isinstance(value, expected):
            return self.fail(path, f"requires {expected.__name__}")
        projected = str(value) if isinstance(value, str) else cast(RootProjection, value).as_dict()
        checked = self.value(projected, contract, path)
        return checked if self.mode == "encode" else value

    def free(self, value: object, path: str) -> object:
        if isinstance(value, enum.Enum):
            return self.enumeration(value, type(value), path)
        if value is None or isinstance(value, str | bool | int):
            return value
        if isinstance(value, float):
            return (
                value
                if math.isfinite(value)
                else self.fail(path, "Non-finite values cannot be published as JSON")
            )
        if isinstance(value, Mapping):
            return self.mapping(value, (str, object), path)
        if isinstance(value, list | tuple):
            return self.sequence(
                value, list if self.mode == "encode" else type(value), (object, Ellipsis), path
            )
        return self.typed(value, type(value), path)

    def unknown(self, values: Mapping[object, object], names: set[str], path: str) -> None:
        unknown = values.keys() - names
        if unknown:
            self.fail(path, "Unknown keys: " + ", ".join(sorted(str(name) for name in unknown)))


def _matches_literal(value: object, choices: tuple[object, ...]) -> bool:
    scalar = value.value if isinstance(value, enum.Enum) else value
    return any(
        type(scalar) is type(choice.value if isinstance(choice, enum.Enum) else choice)
        and scalar == (choice.value if isinstance(choice, enum.Enum) else choice)
        for choice in choices
    )


def _run(
    value: object, annotation: object, mode: Mode, label: str, error: type[OdfA11yError]
) -> object:
    walker = _Walker(mode)
    result = walker.value(value, annotation, label)
    if walker.problems:
        message = f"{label} contains {len(walker.problems)} contract problem(s)"
        raise error(
            message,
            problems=tuple(walker.problems),
        )
    return result


@overload
def decode[T](
    expected: type[T],
    value: object,
    *,
    label: str = "value",
    error: type[OdfA11yError] = InvalidOption,
) -> T: ...


@overload
def decode(
    expected: object,
    value: object,
    *,
    label: str = "value",
    error: type[OdfA11yError] = InvalidOption,
) -> object: ...


def decode(
    expected: object,
    value: object,
    *,
    label: str = "value",
    error: type[OdfA11yError] = InvalidOption,
) -> object:
    """Decode a contract without changing scalar types or accepting unknown fields."""
    return _run(value, expected, "decode", label, error)


def validate(
    value: object,
    expected: object | None = None,
    *,
    label: str = "value",
    error: type[OdfA11yError] = InvalidOption,
) -> None:
    """Validate a typed object directly, without serializing and reparsing it."""
    _run(value, expected or type(value), "validate", label, error)


def encode(value: object, expected: object | None = None) -> JsonValue:
    """Encode fields and computed properties under their annotated constraints."""
    return cast(
        "JsonValue", _run(value, expected or type(value), "encode", "record", InvalidOption)
    )


def record_dict(value: object) -> JsonObject:
    result = encode(value)
    if not isinstance(result, dict):
        message = "A published record must be a JSON object"
        raise InvalidOption(message)
    return result
