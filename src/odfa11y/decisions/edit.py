# SPDX-License-Identifier: AGPL-3.0-only
"""The outcome vocabulary of validated document edits."""

from dataclasses import dataclass, field
from enum import StrEnum

from odfa11y.contracts import JsonObject, record_dict
from odfa11y.errors import Failure
from odfa11y.odf.allowance import Allowance


class Status(StrEnum):
    """The result of one operation on one target."""

    APPLIED = "applied"
    UNCHANGED = "unchanged"
    FAILED = "failed"

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

    kind_id: str
    status: Status
    message: str
    target: str | None = None
    count: int = 0
    failure: Failure | None = None

    def as_dict(self) -> JsonObject:
        """Project this typed edit outcome using the shared contract engine."""
        return record_dict(self)


@dataclass(frozen=True, slots=True)
class EditResult:
    """Outcomes and the exact XML effects an edit permits."""

    outcomes: tuple[Outcome, ...]
    allowance: Allowance = field(default_factory=Allowance)
