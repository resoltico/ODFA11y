# SPDX-License-Identifier: MPL-2.0
"""Immutable batch snapshots derive acceptance from runs and preparation failures."""

import json
from dataclasses import dataclass
from typing import Literal
lazy from pathlib import Path

from odfa11y.contracts import JsonProperty, record_dict
from odfa11y.errors import Failure
from odfa11y.publish import publish_file
from odfa11y.run.record import RunRecord
from odfa11y.status import ExitStatus, combine_statuses
lazy from odfa11y.contracts import JsonObject
lazy from odfa11y.progress import Stage


@dataclass(frozen=True, slots=True)
class BatchItemResult:
    """A pending invocation, a completed run or a preparation failure; never a fabricated run."""

    id: str
    _result: RunRecord | Failure | None = None
    _started: bool = False
    _interrupted: bool = False

    @JsonProperty
    def error(self) -> Failure | None:
        return self._result if isinstance(self._result, Failure) else None

    @JsonProperty
    def evidence(self) -> str | None:
        return self.id if isinstance(self._result, RunRecord) else None

    @JsonProperty
    def failed_stage(self) -> Stage | None:
        return self._result.failed_stage if isinstance(self._result, RunRecord) else None

    @JsonProperty
    def exit_status(self) -> ExitStatus | None:
        if self._interrupted:
            return ExitStatus.EXECUTION_FAILURE
        return self._result.exit_status if self._result is not None else None

    @JsonProperty
    def status(self) -> Literal["pending", "running", "completed", "failed", "interrupted"]:
        """Describe invocation lifetime, deriving acceptance from its actual result."""
        if self._interrupted:
            return "interrupted"
        if self._result is not None:
            return "failed" if self.exit_status else "completed"
        return "running" if self._started else "pending"


@dataclass(frozen=True, slots=True)
class BatchRecord:
    """One durable snapshot of independently executed batch items."""

    items: tuple[BatchItemResult, ...] = ()
    _complete: bool = False
    _interrupted: bool = False

    @JsonProperty
    def exit_status(self) -> ExitStatus:
        if self._interrupted:
            return ExitStatus.EXECUTION_FAILURE
        return combine_statuses(item.exit_status or ExitStatus.PASSED for item in self.items)

    @JsonProperty
    def status(self) -> Literal["running", "completed", "failed", "interrupted"]:
        if self._interrupted:
            return "interrupted"
        if self._complete:
            return "failed" if self.exit_status else "completed"
        return "running"

    @JsonProperty
    def schema_version(self) -> Literal[1]:
        return 1

    @JsonProperty
    def pending_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.items if not item._started)

    def as_dict(self) -> JsonObject:
        """Serialize summary facts without duplicating the per-run evidence records."""
        return record_dict(self)

    def publish(self, output: Path) -> None:
        """Atomically replace batch.json while retaining the previous valid snapshot on failure."""
        payload = (json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n").encode("utf-8")
        publish_file(output / "batch.json", lambda stream: stream.write(payload), replace=True)
