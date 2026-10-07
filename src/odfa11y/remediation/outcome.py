# SPDX-License-Identifier: MPL-2.0
"""The contract every remediation operation implements, and what it reports back."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.odf import OdtDocument


class Status(StrEnum):
    """The result of one operation on one target."""

    APPLIED = "applied"
    UNCHANGED = "unchanged"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Outcome:
    """What an operation did to one target (``key``), or why it could not."""

    operation: str
    status: Status
    message: str
    key: str | None = None
    count: int = 0

    def as_dict(self) -> dict[str, Any]:
        """Serialize this outcome into JSON-compatible values.

        Returns
        -------
        dict[str, Any]
            The outcome with its status as a string.

        """
        return {
            "operation": self.operation,
            "key": self.key,
            "status": self.status.value,
            "count": self.count,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class AltText:
    """Accessible text for a named graphic; ``None`` leaves that field untouched."""

    title: str | None = None
    description: str | None = None


class Operation(ABC):
    """One explicit, deterministic change, fully described by its parameters.

    An operation edits a document only through :meth:`OdtDocument.edit`, reports
    ``APPLIED`` only when it changed something, and ``UNCHANGED`` when its postcondition
    already held, so applying it twice never accumulates changes.
    """

    name: ClassVar[str]

    @abstractmethod
    def apply(self, document: OdtDocument) -> tuple[Outcome, ...]:
        """Apply the change to a document and report one outcome per target.

        Returns
        -------
        tuple[Outcome, ...]
            The outcome for each target the operation addresses.

        """

    def as_dict(self) -> dict[str, Any]:
        """Describe the operation and its parameters in JSON-compatible values.

        Returns
        -------
        dict[str, Any]
            The operation name and parameters.

        """
        parameters = asdict(self) if is_dataclass(self) and not isinstance(self, type) else {}
        return {"operation": self.name, **parameters}


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
