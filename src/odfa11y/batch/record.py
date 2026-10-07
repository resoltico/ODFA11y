# SPDX-License-Identifier: MPL-2.0
"""Atomic, path-free progress records for batch execution."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from odfa11y.staging import staging_sibling

if TYPE_CHECKING:
    from pathlib import Path

BATCH_FORMAT = 1
EXECUTION_FAILURE = 3


@dataclass(slots=True)
class BatchRecord:
    """Aggregate status and relative evidence references in manifest order."""

    items: list[dict[str, Any]] = field(default_factory=list)
    status: str = "running"

    @property
    def exit_status(self) -> int:
        """Execution failures dominate errors, then strict warnings."""
        if self.status == "interrupted":
            return EXECUTION_FAILURE
        return max((item["exit_status"] or 0 for item in self.items), default=0)

    def as_dict(self) -> dict[str, Any]:
        """Serialize progress without input paths.

        Returns
        -------
        dict[str, Any]
            Current status, per-item evidence and IDs not yet executed.

        """
        return {
            "format": BATCH_FORMAT,
            "status": self.status,
            "exit_status": self.exit_status,
            "items": self.items,
            "pending_ids": [item["id"] for item in self.items if item["status"] == "pending"],
        }

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
