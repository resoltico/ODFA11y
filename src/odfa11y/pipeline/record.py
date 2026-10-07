# SPDX-License-Identifier: MPL-2.0
"""The data a pipeline run produces: stage results, options and the run record."""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from odfa11y import __version__
from odfa11y.odf import provenance
from odfa11y.pdf import EXPORT_OPTIONS
from odfa11y.report import exit_status

if TYPE_CHECKING:
    from odfa11y.remediation import RemediationResult
    from odfa11y.report import Report

RECORD_FORMAT = 1
EXECUTION_FAILURE = 3
STAGE_NAMES = (
    "audit-source",
    "remediate",
    "audit-remediated",
    "export-source",
    "export-remediated",
    "audit-pdf",
    "verapdf",
    "fidelity",
)


@dataclass(frozen=True, slots=True)
class StageResult:
    """One stage: ``passed``, ``failed`` or ``skipped``, with its report when it has one."""

    name: str
    status: str
    reason: str | None = None
    report: Report | None = None
    remediation: RemediationResult | None = None
    gate: bool = True
    error: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Serialize the stage.

        Returns
        -------
        dict[str, Any]
            The stage name, status, reason and attached results.

        """
        return {
            "name": self.name,
            "status": self.status,
            "reason": self.reason,
            "report": self.report.as_dict() if self.report else None,
            "remediation": self.remediation.as_dict() if self.remediation else None,
        }


@dataclass(slots=True)
class RunRecord:
    """The ordered stage results of a run and the facts that identify it."""

    input_name: str
    input_sha256: str
    operations: tuple[dict[str, Any], ...]
    policy: dict[str, Any]
    strict: bool
    stages: list[StageResult] = field(default_factory=list)
    toolchain: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)

    @property
    def failed_stage(self) -> str | None:
        """The first failed stage, if any."""
        return next((stage.name for stage in self.stages if stage.status == "failed"), None)

    @property
    def passed(self) -> bool:
        """Whether no stage failed."""
        return self.failed_stage is None

    @property
    def exit_status(self) -> int:
        """3 for an execution failure, else the audit exit status of the gate reports."""
        if any(stage.error for stage in self.stages):
            return EXECUTION_FAILURE
        reports = [stage.report for stage in self.stages if stage.gate and stage.report]
        return exit_status(reports, strict=self.strict)

    def as_dict(self) -> dict[str, Any]:
        """Serialize the record without timestamps or absolute paths.

        Returns
        -------
        dict[str, Any]
            The record written to run.json.

        """
        return {
            "format": RECORD_FORMAT,
            "odfa11y": __version__,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "toolchain": self.toolchain,
            "schemas": {name: entry["sha256"] for name, entry in provenance().items()},
            "export_options": EXPORT_OPTIONS,
            "input": {"name": self.input_name, "sha256": self.input_sha256},
            "operations": list(self.operations),
            "fidelity_policy": self.policy,
            "strict": self.strict,
            "stages": [stage.as_dict() for stage in self.stages],
            "outputs": dict(sorted(self.outputs.items())),
            "status": "passed" if self.passed else "failed",
            "failed_stage": self.failed_stage,
        }


@dataclass(frozen=True, slots=True)
class PipelineOptions:
    """Tool selection and gating: ``verapdf`` is None, ``"auto"`` (search PATH) or a path."""

    soffice: str | None = None
    verapdf: str | None = None
    timeout: int = 120
    strict: bool = False
