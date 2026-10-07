# SPDX-License-Identifier: MPL-2.0
"""What a remediation run reports back."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from odfa11y.adapter import Status

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.adapter import Outcome


@dataclass(frozen=True, slots=True)
class RemediationResult:
    """The outcome of a remediation run; ``destination`` is None for a dry run."""

    source: Path
    destination: Path | None
    outcomes: tuple[Outcome, ...]
    schema_check: str
    dry_run: bool = False
    operations: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @property
    def changed(self) -> bool:
        """Whether any operation changed the document."""
        return any(outcome.status is Status.APPLIED for outcome in self.outcomes)

    def as_dict(self) -> dict[str, Any]:
        """Serialize the run into JSON-compatible values.

        Returns
        -------
        dict[str, Any]
            The file names (not paths), operations, outcomes and schema check result.

        """
        return {
            "source": self.source.name,
            "destination": self.destination.name if self.destination else None,
            "dry_run": self.dry_run,
            "changed": self.changed,
            "schema_check": self.schema_check,
            "operations": list(self.operations),
            "outcomes": [outcome.as_dict() for outcome in self.outcomes],
        }
