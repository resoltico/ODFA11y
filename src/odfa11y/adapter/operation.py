# SPDX-License-Identifier: MPL-2.0
"""The contract every operation implements, and what it reports back."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, is_dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from odfa11y.odf import Family, OdfDocument


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
    removed_blocks: int = 0  # empty body blocks this outcome deleted; the snapshot may shrink by it

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


class Operation(ABC):
    """One explicit, deterministic change, fully described by its parameters.

    An operation edits a document only through :meth:`OdfDocument.edit`, reports
    ``APPLIED`` only when it changed something, and ``UNCHANGED`` when its postcondition
    already held, so applying it twice never accumulates changes. ``family`` names the
    document family the operation belongs to; None means any document.
    """

    name: ClassVar[str]
    family: ClassVar[Family | None] = None

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
