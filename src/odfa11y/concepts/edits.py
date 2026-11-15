# SPDX-License-Identifier: MPL-2.0
"""The contract every operation implements, and what it reports back."""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, is_dataclass
from enum import StrEnum
from typing import Any, ClassVar

from odfa11y.status import StageStatus
lazy from odfa11y.odf import Family, OdfDocument


class Status(StrEnum):
    """The result of one operation on one target."""

    APPLIED = "applied"
    UNCHANGED = "unchanged"
    FAILED = StageStatus.FAILED

    @property
    def meaning(self) -> str:
        """Return the core-owned meaning of this value."""
        return {
            self.APPLIED: "The edit changed XML and established its postcondition.",
            self.UNCHANGED: "The intended postcondition already held without changing XML.",
            self.FAILED: "The edit could not establish its required postcondition.",
        }[self]


@dataclass(frozen=True, slots=True)
class Outcome:
    """What an operation did to one target (``key``), or why it could not."""

    operation: str
    status: Status
    message: str
    target: str | None = None
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
            "target": self.target,
            "status": self.status.value,
            "count": self.count,
            "message": self.message,
        }


class Operation(ABC):
    """One explicit, deterministic change, fully described by its parameters.

    An operation changes live XML through :meth:`OdfDocument.tree`, reports
    ``APPLIED`` only when it changed something, and ``UNCHANGED`` when its postcondition
    already held, so applying it twice never accumulates changes. ``families`` names the
    document families the operation supports; None means any document.
    """

    name: ClassVar[str]
    families: ClassVar[frozenset[Family] | None] = None

    @abstractmethod
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
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
