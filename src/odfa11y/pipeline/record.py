# SPDX-License-Identifier: MPL-2.0
"""The data a pipeline run produces: stage results, options and the run record."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from dataclasses import dataclass, field
from importlib import metadata
from typing import TYPE_CHECKING, Any

from odfa11y import __version__
from odfa11y.odf import provenance
from odfa11y.pdf import EXPORT_OPTIONS
from odfa11y.report import exit_status

from .profiles import DEFAULT_PROFILE, profile_named

if TYPE_CHECKING:
    from odfa11y.remediation import RemediationResult
    from odfa11y.report import Report

    from .profiles import Profile

RECORD_FORMAT = 2
EXECUTION_FAILURE = 3
LOCALE_VARIABLES = ("LANG", "LC_ALL", "LC_MESSAGES")
LIBRARIES = ("lxml", "pillow", "pypdf", "pypdfium2")


@dataclass(frozen=True, slots=True)
class StageResult:
    """One stage: ``passed``, ``failed``, ``skipped`` or ``not-applicable``, with its report.

    ``skipped`` means a stage that could have run did not (an earlier failure, or outside
    the profile); ``not-applicable`` means the kind of document has no such stage.
    """

    name: str
    status: str
    reason: str | None = None
    report: Report | None = None
    remediation: RemediationResult | None = None
    gate: bool = True
    error: bool = False
    details: str | None = None

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
            "details": self.details,
            "report": self.report.as_dict() if self.report else None,
            "remediation": self.remediation.as_dict() if self.remediation else None,
        }


@dataclass(slots=True)
class RunRecord:
    """The ordered stage results of a run and the facts that identify it."""

    document: dict[str, Any]
    operations: tuple[dict[str, Any], ...]
    policy: dict[str, Any]
    profile: Profile
    stages: list[StageResult] = field(default_factory=list)
    toolchain: dict[str, Any] = field(default_factory=dict)
    fonts: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    human_review: list[dict[str, str]] = field(default_factory=list)
    outputs: dict[str, str] = field(default_factory=dict)

    @property
    def strict(self) -> bool:
        """Whether warnings fail the gates."""
        return self.profile.strict

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

    @property
    def plan_sha256(self) -> str:
        """Digest of the operations, fidelity policy and profile, independent of file layout."""
        plan = {
            "operations": list(self.operations),
            "fidelity_policy": self.policy,
            "profile": self.profile.as_dict(),
        }
        return hashlib.sha256(json.dumps(plan, sort_keys=True).encode("utf-8")).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        """Serialize the record without timestamps; paths are redacted when it is written.

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
            "environment": {name: os.environ.get(name) for name in LOCALE_VARIABLES},
            "libraries": _library_versions(),
            "toolchain": self.toolchain,
            "schemas": {name: entry["sha256"] for name, entry in provenance().items()},
            "export_options": EXPORT_OPTIONS,
            "document": self.document,
            "plan_sha256": self.plan_sha256,
            "profile": self.profile.as_dict(),
            "operations": list(self.operations),
            "fidelity_policy": self.policy,
            "stages": [stage.as_dict() for stage in self.stages],
            "fonts": self.fonts,
            "human_review": self.human_review,
            "outputs": dict(sorted(self.outputs.items())),
            "status": "passed" if self.passed else "failed",
            "failed_stage": self.failed_stage,
        }


def _library_versions() -> dict[str, str]:
    versions = {}
    for name in LIBRARIES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "unknown"
    return versions


@dataclass(frozen=True, slots=True)
class PipelineOptions:
    """Tool locations, the time limit and the assurance profile."""

    profile: str = DEFAULT_PROFILE
    soffice: str | None = None
    verapdf_path: str | None = None
    timeout: int = 120

    @property
    def assurance(self) -> Profile:
        """The selected assurance profile."""
        return profile_named(self.profile)
