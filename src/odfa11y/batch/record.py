# SPDX-License-Identifier: MPL-2.0
"""Atomic, path-free progress records for batch execution."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from odfa11y.outcomes import BatchStatus, ExitStatus, combine_statuses
from odfa11y.serialization import JsonProperty, record_dict
from odfa11y.staging import staging_sibling

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.outcomes import StageName
    from odfa11y.serialization import JsonObject

BATCH_FORMAT = 2


@dataclass(slots=True)
class BatchItemResult:
    """One manifest item's execution lifetime and relative evidence reference."""

    id: str
    status: BatchStatus = BatchStatus.PENDING
    exit_status: ExitStatus | None = None
    failed_stage: StageName | None = None
    evidence: str | None = None


@dataclass(slots=True)
class BatchRecord:
    """Aggregate status and relative evidence references in manifest order."""

    items: list[BatchItemResult] = field(default_factory=list)
    status: BatchStatus = BatchStatus.RUNNING

    @JsonProperty
    def exit_status(self) -> ExitStatus:
        """Execution failures dominate errors, then strict warnings."""
        if self.status == BatchStatus.INTERRUPTED:
            return ExitStatus.EXECUTION_FAILURE
        return combine_statuses(item.exit_status or ExitStatus.PASSED for item in self.items)

    @JsonProperty
    def format(self) -> Literal[2]:
        """The batch record format version."""
        return BATCH_FORMAT

    @JsonProperty
    def pending_ids(self) -> list[str]:
        """Manifest IDs whose work has not started."""
        return [item.id for item in self.items if item.status == BatchStatus.PENDING]

    def as_dict(self) -> JsonObject:
        """Serialize the typed batch progress.

        Returns
        -------
        JsonObject
            Aggregate and per-item execution status.

        """
        return record_dict(self)

    def publish(self, output: Path) -> None:
        """Replace batch.json atomically, retaining the previous valid record on failure."""
        destination = output / "batch.json"
        temporary = staging_sibling(destination)
        try:
            temporary.write_text(
                json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
