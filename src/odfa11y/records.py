# SPDX-License-Identifier: MPL-2.0
"""Typed identities and assurance measurements shared by workflow records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from odfa11y.serialization import record_dict
lazy from odfa11y.outcomes import StageStatus

if TYPE_CHECKING:
    from odfa11y.native.process import ToolIdentity
    from odfa11y.serialization import JsonObject


@dataclass(slots=True)
class DocumentIdentity:
    """Captured source identity and its established document kind."""

    name: str
    sha256: str | None = None
    kind: str | None = None
    media_type: str | None = None
    layout: str | None = None
    family: str | None = None
    adapter: str | None = None
    odf_version: str | None = None


@dataclass(slots=True)
class Toolchain:
    """Native identities and measured capabilities, without executable paths."""

    libreoffice: ToolIdentity | None = None
    verapdf: ToolIdentity | None = None
    capabilities: dict[str, str | None] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SchemaCheck:
    """The selected schema, before/after counts and established regression count."""

    status: StageStatus
    version: str | None
    before_count: int | None
    after_count: int | None
    new_count: int | None = 0
    unlocated_count: int | None = 0

    def as_dict(self) -> JsonObject:
        """Serialize schema assurance independently of human-readable prose.

        Returns
        -------
        JsonObject
            Version, status and violation counts.

        """
        return record_dict(self)


@dataclass(slots=True)
class DoctorRecord:
    """Tool/dependency identities and measured capabilities for one environment."""

    odfa11y: str
    python: str
    platform: str
    libraries: dict[str, str]
    schema_versions: tuple[str, ...]
    toolchain: Toolchain
    capabilities: dict[str, str | None] = field(default_factory=dict)
    format: Literal[1] = field(default=1, init=False)

    def as_dict(self) -> JsonObject:
        """Serialize the typed environment record.

        Returns
        -------
        JsonObject
            Versioned tool, dependency and capability facts.

        """
        return record_dict(self)
