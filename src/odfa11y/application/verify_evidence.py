# SPDX-License-Identifier: MPL-2.0
"""Verify evidence application use case."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from odfa11y.application.io_errors import translate_io
from odfa11y.contracts import JsonObject, JsonProperty, record_dict
from odfa11y.evidence import check_bundle
from odfa11y.status import ExitStatus


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Recorded-file integrity problems, independent of accessibility claims."""

    schema_version: Literal[1] = field(default=1, init=False)

    problems: tuple[str, ...]

    @JsonProperty
    def exit_status(self) -> ExitStatus:
        """Whether every recorded integrity check passed."""
        return ExitStatus.ERRORS if self.problems else ExitStatus.PASSED

    def as_dict(self) -> JsonObject:
        """Serialize the use case's result contract."""
        return record_dict(self)


@translate_io
def verify_evidence(directory: str | Path) -> VerificationResult:
    """Check recorded file integrity without claiming document accessibility.

    Returns
    -------
    VerificationResult
        Every integrity problem and effective status.

    """
    return VerificationResult(tuple(check_bundle(directory)))
