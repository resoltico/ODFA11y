# SPDX-License-Identifier: MPL-2.0
"""Options and results for explicit ODT remediation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(slots=True)
class RemediationResult:
    """Describe a saved document and the changes applied."""

    source: Path
    destination: Path
    changes: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class AltText:
    """Provide accessible text for a named graphic."""

    title: str | None = None
    description: str | None = None


@dataclass(slots=True, frozen=True)
class RemediationOptions:
    """Select explicit, conservative document changes."""

    target_version: str | None = "1.4"
    title: str | None = None
    description: str | None = None
    language: str | None = None
    linkify_plain_addresses: bool = False
    remove_empty_spacers: bool = False
    table_header_rows: dict[str, int] | None = None
    alt_text: dict[str, AltText] | None = None
