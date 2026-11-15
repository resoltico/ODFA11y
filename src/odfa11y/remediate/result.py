# SPDX-License-Identifier: MPL-2.0
"""What a remediation run reports back."""

from dataclasses import dataclass, field
from typing import Literal
lazy from pathlib import Path

from odfa11y.concepts.edits import Status
from odfa11y.serialization import JsonProperty, record_dict
from odfa11y.status import ExitStatus
lazy from odfa11y.concepts.edits import Outcome
lazy from odfa11y.records import SchemaCheck
lazy from odfa11y.remediate.violations import ViolationKind
lazy from odfa11y.serialization import JsonObject


@dataclass(frozen=True, slots=True)
class Violation:
    """One failed preservation, outcome, identity or schema guard."""

    kind: ViolationKind
    message: str
    operation: str | None = None
    key: str | None = None


@dataclass(frozen=True, slots=True)
class RemediationResult:
    """The outcome of a remediation run; ``destination`` is None for a dry run."""

    source: Path = field(metadata={"basename": True})
    destination: Path | None = field(metadata={"basename": True})
    outcomes: tuple[Outcome, ...]
    schema: SchemaCheck
    format: Literal[1] = field(default=1, init=False)
    published: bool = False
    violations: tuple[Violation, ...] = ()
    rebind: bool = False
    dry_run: bool = False
    operations: tuple[JsonObject, ...] = field(default_factory=tuple)

    @JsonProperty
    def changed(self) -> bool:
        """Whether any operation changed the document."""
        return any(outcome.status is Status.APPLIED for outcome in self.outcomes)

    @JsonProperty
    def exit_status(self) -> ExitStatus:
        """Whether the requested checks succeeded, including valid unpublished previews."""
        return (
            ExitStatus.PASSED
            if not self.violations and (self.published or self.dry_run)
            else ExitStatus.ERRORS
        )

    def as_dict(self) -> JsonObject:
        """Serialize typed remediation outcomes and schema assurance.

        Returns
        -------
        JsonObject
            Basenames, operations, outcomes and structured schema assurance.

        """
        return record_dict(self)
