# SPDX-License-Identifier: MPL-2.0
"""The data a pipeline run produces: stage results, options and the run record."""

import hashlib
import json
import os
import platform
import sys
from dataclasses import dataclass, field
from importlib import metadata
from typing import Literal

from odfa11y.contracts import JsonProperty, record_dict
from odfa11y.native.export import EXPORT_OPTIONS
from odfa11y.odf import provenance
from odfa11y.plans import Plan
from odfa11y.records import Toolchain
from odfa11y.report import exit_status
from odfa11y.status import ExitStatus, RunStatus, StageStatus, combine_statuses
from odfa11y.version import __version__
lazy from odfa11y.contracts import JsonObject
lazy from odfa11y.decisions import Decision
lazy from odfa11y.families.spec import ReviewItem
lazy from odfa11y.plans import PlanHeader
lazy from odfa11y.plans.fidelity import FidelityPolicy
lazy from odfa11y.progress import Stage
lazy from odfa11y.records import DocumentIdentity
lazy from odfa11y.remediate import RemediationResult
lazy from odfa11y.report import Report
lazy from odfa11y.run.profiles import Profile

RECORD_SCHEMA_VERSION = 1
LOCALE_VARIABLES = ("LANG", "LC_ALL", "LC_MESSAGES")
LIBRARIES = ("lxml", "pillow", "pypdf", "pypdfium2")


@dataclass(frozen=True, slots=True)
class StageResult:
    """One stage: ``passed``, ``failed``, ``skipped`` or ``not-applicable``, with its report.

    ``skipped`` means a stage that could have run did not (an earlier failure, or outside
    the profile); ``not-applicable`` means the kind of document has no such stage.
    """

    name: Stage
    status: StageStatus
    reason: str | None = None
    report: Report | None = None
    remediation: RemediationResult | None = None
    _gate: bool = field(default=True)
    _error: bool = field(default=False)
    details: str | None = None
    _failure_status: ExitStatus = field(default=ExitStatus.EXECUTION_FAILURE)

    def as_dict(self) -> JsonObject:
        """Serialize the typed execution record.

        Returns
        -------
        JsonObject
            Published fields and computed assurance measurements.

        """
        return record_dict(self)

    @property
    def gate(self) -> bool:
        return self._gate

    @property
    def error(self) -> bool:
        return self._error

    @property
    def failure_status(self) -> ExitStatus:
        return self._failure_status


@dataclass(slots=True)
class RunRecord:
    """The ordered stage results of a run and the facts that identify it."""

    document: DocumentIdentity
    fidelity_policy: FidelityPolicy
    profile: Profile
    stages: list[StageResult] = field(default_factory=list)
    toolchain: Toolchain = field(default_factory=Toolchain)
    fonts: dict[str, list[dict[str, object]]] = field(default_factory=dict)
    human_review: tuple[ReviewItem, ...] = ()
    outputs: dict[str, str] = field(default_factory=dict)
    plan: PlanHeader | None = None
    decisions: tuple[Decision, ...] = ()

    @property
    def strict(self) -> bool:
        """Whether warnings fail the gates."""
        return self.profile.strict

    @JsonProperty
    def failed_stage(self) -> Stage | None:
        """The first failed stage, if any."""
        return next(
            (stage.name for stage in self.stages if stage.status == StageStatus.FAILED), None
        )

    @property
    def passed(self) -> bool:
        """Whether no stage failed."""
        return self.failed_stage is None

    @JsonProperty
    def exit_status(self) -> ExitStatus:
        """Combine execution, usage and finding outcomes by explicit precedence."""
        reports = [stage.report for stage in self.stages if stage.gate and stage.report]
        return combine_statuses([
            exit_status(reports, strict=self.strict),
            *(stage.failure_status for stage in self.stages if stage.error),
            *(stage.remediation.exit_status for stage in self.stages if stage.remediation),
        ])

    @JsonProperty
    def plan_sha256(self) -> str:
        """Digest of the operations, fidelity policy and profile, independent of file layout."""
        plan = {
            "plan": Plan(self.plan, self.decisions, self.fidelity_policy).as_dict()
            if self.plan
            else None,
            "fidelity_policy": self.fidelity_policy.as_dict(),
            "profile": self.profile.as_dict(),
        }
        return hashlib.sha256(json.dumps(plan, sort_keys=True).encode("utf-8")).hexdigest()

    def as_dict(self) -> JsonObject:
        """Serialize the typed execution record.

        Returns
        -------
        JsonObject
            Published fields and computed assurance measurements.

        """
        return record_dict(self)

    @JsonProperty
    def schema_version(self) -> Literal[1]:
        """The run record's schema version."""
        return RECORD_SCHEMA_VERSION

    @JsonProperty
    def odfa11y(self) -> str:
        """The generator version."""
        return __version__

    @JsonProperty
    def python(self) -> str:
        """The interpreter version."""
        return sys.version.split()[0]

    @JsonProperty
    def platform(self) -> str:
        """The execution platform identity."""
        return platform.platform()

    @JsonProperty
    def environment(self) -> dict[str, str | None]:
        """The locale variables affecting native execution."""
        return {name: os.environ.get(name) for name in LOCALE_VARIABLES}

    @JsonProperty
    def libraries(self) -> dict[str, str]:
        """Installed runtime dependency versions."""
        return _library_versions()

    @JsonProperty
    def schemas(self) -> dict[str, str]:
        """Digests of bundled normative schema inputs."""
        return {name: entry["sha256"] for name, entry in provenance().items()}

    @JsonProperty
    def export_options(self) -> dict[str, dict[str, str]]:
        """The authoritative LibreOffice export options."""
        return EXPORT_OPTIONS

    @JsonProperty
    def status(self) -> RunStatus:
        """Whether all required assurance gates passed."""
        return RunStatus.PASSED if self.passed else RunStatus.FAILED


def _library_versions() -> dict[str, str]:
    versions = {}
    for name in LIBRARIES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "unknown"
    return versions
