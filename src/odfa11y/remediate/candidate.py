# SPDX-License-Identifier: MPL-2.0
"""A verified in-memory candidate and an explicit refusal without an artifact."""

from dataclasses import dataclass
from pathlib import Path

from odfa11y.errors import DocumentRefusal
from odfa11y.odf import OdfDocument
from odfa11y.odf.document import DocumentCheckpoint
from odfa11y.remediate.result import RemediationResult


@dataclass(frozen=True, slots=True)
class Candidate:
    document: OdfDocument
    checkpoint: DocumentCheckpoint
    result: RemediationResult

    def materialize(self, destination: Path) -> Path:
        if self.document.changed_since(self.checkpoint):
            message = "Candidate changed after its preservation and schema checks"
            raise DocumentRefusal(message)
        return self.document.save(destination)


@dataclass(frozen=True, slots=True)
class RefusedCandidate:
    result: RemediationResult
