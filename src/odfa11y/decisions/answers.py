# SPDX-License-Identifier: MPL-2.0
"""Shared answer fields, constraints and help for cross-family human decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class GraphicAlternativeAnswer:
    """Authored accessible text and an explicit meaning/decorative role."""

    title: str | None = field(
        default=None,
        metadata={"schema": {"description": "Accessible title; empty text explicitly clears it."}},
    )
    description: str | None = field(
        default=None,
        metadata={
            "schema": {"description": "Explain the graphic's meaning; empty text clears it."}
        },
    )
    decorative: bool | None = field(
        default=None,
        metadata={
            "schema": {"description": "Explicit decorative role, subject to source safety guards."}
        },
    )
    required_any: ClassVar[tuple[str, ...]] = ("title", "description", "decorative")


@dataclass(frozen=True, slots=True)
class LinkDescriptionAnswer:
    """A supplied description without changing visible text or destination."""

    description: str = field(
        metadata={
            "schema": {
                "pattern": r"\S",
                "description": "Explain the link's purpose in its reading context.",
            }
        }
    )


@dataclass(frozen=True, slots=True)
class PageMetadataAnswer:
    """Explicit page title and purpose."""

    title: str | None = field(
        default=None, metadata={"schema": {"description": "Accessible page title."}}
    )
    description: str | None = field(
        default=None, metadata={"schema": {"description": "Page purpose and context."}}
    )
    required_any: ClassVar[tuple[str, ...]] = ("title", "description")


@dataclass(frozen=True, slots=True)
class PageNavigationAnswer:
    """A reviewed complete order of native shape identities."""

    navigation: tuple[str, ...] = field(
        metadata={
            "schema": {
                "items": {"type": "string", "pattern": r"\S"},
                "description": "Complete reading order of the page's existing shape identities.",
            }
        }
    )


@dataclass(frozen=True, slots=True)
class SwitchAnswer:
    """Explicit consent or refusal for a document-wide operation."""

    enabled: bool = field(
        metadata={"schema": {"description": "Enable only after reviewing all affected content."}}
    )


@dataclass(frozen=True, slots=True)
class FormulaAlternativeAnswer:
    """The spoken meaning of the native mathematical expression."""

    alternative: str = field(
        metadata={
            "schema": {
                "pattern": r"\S",
                "description": "Write the formula's spoken meaning in its intended language.",
            }
        }
    )


@dataclass(frozen=True, slots=True)
class DatabaseDescriptionAnswer:
    """Human-supplied meaning for an existing declared database object."""

    text: str = field(
        metadata={
            "schema": {
                "pattern": r"\S",
                "description": "Explain the declared object without changing SQL or bindings.",
            }
        }
    )
