# SPDX-License-Identifier: AGPL-3.0-only
"""What a remediation run reports back."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal
lazy from pathlib import Path

from odfa11y.contracts import JsonProperty, record_dict
from odfa11y.decisions.edit import Outcome, Status
from odfa11y.status import ExitStatus
lazy from odfa11y.contracts import JsonObject
lazy from odfa11y.decisions import Decision
lazy from odfa11y.remediate.violations import ViolationKind
lazy from odfa11y.report import Finding, Report
lazy from odfa11y.targets import TargetPath


@dataclass(frozen=True, slots=True)
class SchemaCheck:
    """The selected schema, before/after counts and established regression count."""

    version: str | None
    before_count: int | None
    after_count: int | None
    new_count: int | None = 0
    unlocated_count: int | None = 0

    @JsonProperty
    def status(self) -> Literal["passed", "failed", "skipped"]:
        if self.after_count is None:
            return "skipped"
        return "failed" if self.new_count else "passed"

    def as_dict(self) -> JsonObject:
        """Serialize schema assurance independently of human-readable prose.

        Returns
        -------
        JsonObject
            Version, status and violation counts.

        """
        return record_dict(self)


@dataclass(frozen=True, slots=True)
class Violation:
    """One failed preservation, outcome, identity or schema guard."""

    kind: ViolationKind
    message: str
    kind_id: str | None = None
    target: str | None = None


@dataclass(frozen=True, slots=True)
class UnansweredReview:
    """An inert answer block and any warning about its stale source target."""

    kind_id: str
    target: TargetPath | None
    stale: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class DecisionPrediction:
    """Findings resolved by an answer and related findings remaining in the candidate."""

    kind_id: str
    target: TargetPath | None
    resolved: tuple[Finding, ...]
    remaining: tuple[Finding, ...]


class PublicationState(StrEnum):
    PUBLISHED = "published"
    PREVIEW = "preview"
    REFUSED = "refused"

    @property
    def meaning(self) -> str:
        return {
            self.PUBLISHED: "The verified candidate was published to the selected output.",
            self.PREVIEW: "The verified candidate is a preview and was not published.",
            self.REFUSED: "A required guard refused the candidate before publication.",
        }[self]


@dataclass(frozen=True, slots=True)
class RemediationResult:
    """The outcome of a remediation run; ``destination`` is None for a dry run."""

    _source: Path
    _destination: Path | None
    outcomes: tuple[Outcome, ...]
    schema: SchemaCheck
    schema_version: Literal[1] = field(default=1, init=False)
    publication: PublicationState = PublicationState.REFUSED
    violations: tuple[Violation, ...] = ()
    decisions: tuple[Decision, ...] = ()
    predictions: tuple[DecisionPrediction, ...] = ()
    candidate: Report | None = None
    unanswered: tuple[UnansweredReview, ...] = ()

    @property
    def published(self) -> bool:
        return self.publication is PublicationState.PUBLISHED

    @property
    def dry_run(self) -> bool:
        return self.publication is PublicationState.PREVIEW

    @JsonProperty
    def changed(self) -> bool:
        """Whether any operation changed the document."""
        return any(outcome.status is Status.APPLIED for outcome in self.outcomes)

    @JsonProperty
    def exit_status(self) -> ExitStatus:
        """Whether the requested checks succeeded, including valid unpublished previews."""
        return (
            ExitStatus.PASSED
            if not self.violations and (self.published or self.dry_run)
            else ExitStatus.ERRORS
        )

    def as_dict(self) -> JsonObject:
        """Serialize typed remediation outcomes and schema assurance.

        Returns
        -------
        JsonObject
            Basenames, operations, outcomes and structured schema assurance.

        """
        return record_dict(self)

    @property
    def source(self) -> Path:
        return self._source

    @property
    def destination(self) -> Path | None:
        return self._destination

    @JsonProperty
    def source_name(self) -> str:
        return self._source.name

    @JsonProperty
    def destination_name(self) -> str | None:
        return self._destination.name if self._destination is not None else None
