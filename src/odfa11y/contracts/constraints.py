# SPDX-License-Identifier: AGPL-3.0-only
"""Typed constraints share validation and JSON Schema semantics."""

import re
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from odfa11y.language_tags import normalize_language

INVALID_XML_CHARACTER = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\uD800-\uDFFF\uFFFE\uFFFF]")


class Constraint(ABC):
    """One annotation-owned rule for an input or record value."""

    @abstractmethod
    def problems(self, value: object) -> tuple[str, ...]:
        """Describe violated conditions without transforming the value."""

    @abstractmethod
    def schema(self) -> dict[str, object]:
        """Return the JSON Schema keywords enforcing the same condition."""


@dataclass(frozen=True, slots=True)
class Description:
    text: str

    def schema(self) -> dict[str, object]:
        return {"description": self.text}


@dataclass(frozen=True, slots=True)
class Pattern(Constraint):
    expression: str

    def problems(self, value: object) -> tuple[str, ...]:
        return (
            ("does not match its required syntax",)
            if value is not None
            and isinstance(value, str)
            and re.search(self.expression, value) is None
            else ()
        )

    def schema(self) -> dict[str, object]:
        return {"pattern": self.expression}


@dataclass(frozen=True, slots=True)
class Length(Constraint):
    minimum: int | None = None
    maximum: int | None = None

    def problems(self, value: object) -> tuple[str, ...]:
        if not isinstance(value, str):
            return ()
        if self.minimum is not None and len(value) < self.minimum:
            return (f"requires at least {self.minimum} characters",)
        if self.maximum is not None and len(value) > self.maximum:
            return (f"allows at most {self.maximum} characters",)
        return ()

    def schema(self) -> dict[str, object]:
        return {
            **({"minLength": self.minimum} if self.minimum is not None else {}),
            **({"maxLength": self.maximum} if self.maximum is not None else {}),
        }


@dataclass(frozen=True, slots=True)
class ItemCount(Constraint):
    minimum: int | None = None
    maximum: int | None = None

    def problems(self, value: object) -> tuple[str, ...]:
        if not isinstance(value, tuple | list):
            return ()
        if self.minimum is not None and len(value) < self.minimum:
            return (f"requires at least {self.minimum} items",)
        if self.maximum is not None and len(value) > self.maximum:
            return (f"allows at most {self.maximum} items",)
        return ()

    def schema(self) -> dict[str, object]:
        return {
            **({"minItems": self.minimum} if self.minimum is not None else {}),
            **({"maxItems": self.maximum} if self.maximum is not None else {}),
        }


@dataclass(frozen=True, slots=True)
class Choices(Constraint):
    values: tuple[object, ...]

    def problems(self, value: object) -> tuple[str, ...]:
        scalar = value.value if isinstance(value, Enum) else value
        choices = tuple(
            choice.value if isinstance(choice, Enum) else choice for choice in self.values
        )
        return (
            ()
            if value is None
            or any(type(scalar) is type(choice) and scalar == choice for choice in choices)
            else (f"must be one of {choices}",)
        )

    def schema(self) -> dict[str, object]:
        return {
            "enum": [choice.value if isinstance(choice, Enum) else choice for choice in self.values]
        }


@dataclass(frozen=True, slots=True)
class Range(Constraint):
    minimum: int | float | None = None
    maximum: int | float | None = None

    def problems(self, value: object) -> tuple[str, ...]:
        if not isinstance(value, int | float) or isinstance(value, bool):
            return ()
        if self.minimum is not None and value < self.minimum:
            return (f"must be at least {self.minimum}",)
        if self.maximum is not None and value > self.maximum:
            return (f"must be at most {self.maximum}",)
        return ()

    def schema(self) -> dict[str, object]:
        return {
            **({"minimum": self.minimum} if self.minimum is not None else {}),
            **({"maximum": self.maximum} if self.maximum is not None else {}),
        }


@dataclass(frozen=True, slots=True)
class NonBlank(Constraint):
    def problems(self, value: object) -> tuple[str, ...]:
        return (
            ("must be non-blank after stripping",)
            if isinstance(value, str) and not value.strip()
            else ()
        )

    def schema(self) -> dict[str, object]:
        return {"pattern": r"\S"}


@dataclass(frozen=True, slots=True)
class XmlText(Constraint):
    format_name: ClassVar[str] = "odfa11y-xml-text"

    def problems(self, value: object) -> tuple[str, ...]:
        return (
            ("contains a character XML 1.0 cannot represent",)
            if isinstance(value, str) and INVALID_XML_CHARACTER.search(value)
            else ()
        )

    def schema(self) -> dict[str, object]:
        return {"format": self.format_name}


@dataclass(frozen=True, slots=True)
class LanguageTag(Constraint):
    format_name: ClassVar[str] = "odfa11y-language-tag"

    def problems(self, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if not isinstance(value, str):
            return ("requires a language tag string",)
        try:
            normalize_language(value)
        except ValueError as error:
            return (str(error),)
        return ()

    def schema(self) -> dict[str, object]:
        return {"format": self.format_name}


@dataclass(frozen=True, slots=True)
class PathSafeName(Constraint):
    format_name: ClassVar[str] = "odfa11y-path-safe-name"

    def problems(self, value: object) -> tuple[str, ...]:
        if not isinstance(value, str):
            return ()
        if not value or value in {".", ".."} or value.endswith((".", " ")):
            return ("requires a portable path component",)
        if re.search(r'[\x00-\x1f\x7f/\\:<>"|?*]', value):
            return ("contains an unsafe path character",)
        base = value.partition(".")[0].upper()
        if base in {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10)),
        }:
            return ("is reserved by the operating system",)
        return ()

    def schema(self) -> dict[str, object]:
        return {"format": self.format_name}


@dataclass(frozen=True, slots=True)
class RequireAny(Constraint):
    fields: tuple[str, ...]

    def problems(self, value: object) -> tuple[str, ...]:
        values = (
            value
            if isinstance(value, Mapping)
            else {name: getattr(value, name, None) for name in self.fields}
        )
        return (
            ()
            if any(values.get(name) is not None for name in self.fields)
            else ("requires at least one of " + ", ".join(self.fields),)
        )

    def schema(self) -> dict[str, object]:
        return {
            "anyOf": [
                {"required": [name], "properties": {name: {"not": {"type": "null"}}}}
                for name in self.fields
            ]
        }


@dataclass(frozen=True, slots=True)
class ExclusiveWhen(Constraint):
    field: str
    value: object
    excludes: tuple[str, ...]

    def problems(self, value: object) -> tuple[str, ...]:
        values = (
            value
            if isinstance(value, Mapping)
            else {name: getattr(value, name, None) for name in (self.field, *self.excludes)}
        )
        if (
            type(values.get(self.field)) is type(self.value)
            and values.get(self.field) == self.value
            and any(values.get(name) is not None for name in self.excludes)
        ):
            return (f"{self.field} = {self.value!r} cannot include " + ", ".join(self.excludes),)
        return ()

    def schema(self) -> dict[str, object]:
        return {
            "if": {"required": [self.field], "properties": {self.field: {"const": self.value}}},
            "then": {"properties": {name: {"type": "null"} for name in self.excludes}},
        }
