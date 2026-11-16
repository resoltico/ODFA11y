# SPDX-License-Identifier: MPL-2.0
"""Typed identities and assurance measurements shared by workflow records."""

from dataclasses import dataclass
from typing import Literal

from odfa11y.contracts import JsonProperty, record_dict
from odfa11y.tool_identity import ToolIdentity
lazy from odfa11y.contracts import JsonObject


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
class Toolchain:
    """Native tool identities without executable paths or environment experiments."""

    libreoffice: ToolIdentity | None = None
    verapdf: ToolIdentity | None = None


@dataclass(frozen=True, slots=True)
class SchemaCheck:
    """The selected schema, before/after counts and established regression count."""

    version: str | None
    before_count: int | None
    after_count: int | None
    new_count: int | None = 0
    unlocated_count: int | None = 0

    @JsonProperty
    def status(self) -> Literal["passed", "failed", "skipped"]:
        if self.after_count is None:
            return "skipped"
        return "failed" if self.new_count else "passed"

    def as_dict(self) -> JsonObject:
        """Serialize schema assurance independently of human-readable prose.

        Returns
        -------
        JsonObject
            Version, status and violation counts.

        """
        return record_dict(self)
