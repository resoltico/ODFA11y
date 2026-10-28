# SPDX-License-Identifier: MPL-2.0
"""What a remediation run reports back."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from odfa11y.adapter import Status
from odfa11y.serialization import JsonProperty, record_dict
lazy from odfa11y.records import SchemaCheck

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.adapter import Outcome
    from odfa11y.serialization import JsonObject


@dataclass(frozen=True, slots=True)
class RemediationResult:
    """The outcome of a remediation run; ``destination`` is None for a dry run."""

    source: Path = field(metadata={"basename": True})
    destination: Path | None = field(metadata={"basename": True})
    outcomes: tuple[Outcome, ...]
    schema: SchemaCheck
    format: Literal[1] = field(default=1, init=False)
    dry_run: bool = False
    operations: tuple[JsonObject, ...] = field(default_factory=tuple)

    @JsonProperty
    def changed(self) -> bool:
        """Whether any operation changed the document."""
        return any(outcome.status is Status.APPLIED for outcome in self.outcomes)

    def as_dict(self) -> JsonObject:
        """Serialize typed remediation outcomes and schema assurance.

        Returns
        -------
        JsonObject
            Basenames, operations, outcomes and structured schema assurance.

        """
        return record_dict(self)
