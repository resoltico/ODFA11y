# SPDX-License-Identifier: MPL-2.0
"""Source-bound plans of answered human decisions and fidelity policy."""

from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Literal
lazy from collections.abc import Iterable

from odfa11y.capture import CapturedSource, source_digest
from odfa11y.contracts import (
    Description,
    JsonObject,
    JsonProperty,
    Length,
    Pattern,
    record_dict,
    validate,
)
from odfa11y.decisions import DecisionScope
from odfa11y.errors import PlanError, Remedy, RemedyAction
from odfa11y.plans.fidelity import FidelityPolicy, Pagination
from odfa11y.targets import TargetPath
lazy from odfa11y.decisions import Decision, DecisionKind
lazy from odfa11y.plans.contracts import to_file

SOURCE_SHA256_PATTERN = r"^[0-9a-f]{64}(?![\s\S])"
PLAN_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class SourceBinding:
    """Exact physical source bytes to which human decisions were bound."""

    sha256: Annotated[
        str, Pattern(SOURCE_SHA256_PATTERN), Description("SHA-256 of the reviewed source bytes.")
    ]


@dataclass(frozen=True, slots=True)
class PlanHeader:
    """The plan format, exact source binding and generator version."""

    schema_version: Literal[1]
    source: SourceBinding
    generator: Annotated[str, Length(minimum=1), Description("Version that generated the plan.")]


@dataclass(frozen=True, slots=True)
class UnansweredDecision:
    """An inert plan block whose answer has not been supplied."""

    _kind: DecisionKind
    path: TargetPath | None
    fingerprint: str | None = None

    def __post_init__(self) -> None:
        if (self.kind.scope is DecisionScope.TARGET) != (self.path is not None):
            message = "An unanswered question must agree with its kind's target scope"
            raise PlanError(message)

    @property
    def kind(self) -> DecisionKind:
        return self._kind

    @JsonProperty
    def kind_id(self) -> str:
        return self.kind.id


@dataclass(frozen=True, slots=True)
class Plan:
    """A bound set of answers, with no legacy configuration or operation-list form."""

    header: PlanHeader
    decisions: tuple[Decision, ...] = ()
    fidelity: FidelityPolicy = field(default_factory=Pagination.SAME)
    unanswered: tuple[UnansweredDecision, ...] = ()

    def __post_init__(self) -> None:
        """Reject conflicting duplicate answers before execution.

        Raises
        ------
        PlanError
            More than one answer addresses the same kind and target.

        """
        validate(self.header, label="plan", error=PlanError)
        validate(self.fidelity, label="fidelity", error=PlanError)
        validate(
            self.unanswered, tuple[UnansweredDecision, ...], label="unanswered", error=PlanError
        )
        self._require_unique_questions()

    def _require_unique_questions(self) -> None:
        keys = [
            (answer.kind.id, answer.target.path if answer.target else None)
            for answer in self.decisions
        ]
        keys.extend((question.kind.id, question.path) for question in self.unanswered)
        if len(keys) != len(set(keys)):
            message = "A plan cannot answer or retain the same decision kind and target twice"
            raise PlanError(message)

    @classmethod
    def _decoded(
        cls,
        header: PlanHeader,
        decisions: tuple[Decision, ...],
        fidelity: FidelityPolicy,
        unanswered: tuple[UnansweredDecision, ...] = (),
    ) -> Plan:
        result = object.__new__(cls)
        object.__setattr__(result, "header", header)
        object.__setattr__(result, "decisions", decisions)
        object.__setattr__(result, "fidelity", fidelity)
        object.__setattr__(result, "unanswered", unanswered)
        result._require_unique_questions()
        return result

    @classmethod
    def for_source(
        cls,
        source: CapturedSource | str | Path,
        decisions: Iterable[Decision] = (),
        *,
        fidelity: FidelityPolicy | None = None,
    ) -> Plan:
        """Bind programmatically reviewed decisions to the current source.

        Returns
        -------
        Plan
            A plan with a mandatory source header.

        """
        return cls(
            PlanHeader(
                PLAN_SCHEMA_VERSION,
                SourceBinding(
                    source.digest
                    if isinstance(source, CapturedSource)
                    else source_digest(Path(source))
                ),
                version("odfa11y"),
            ),
            tuple(decisions),
            fidelity or Pagination.SAME(),
        )

    def verify_source(self, source: str | Path) -> None:
        """Require exactly the source bytes reviewed by this plan."""
        if source_digest(Path(source)) != self.header.source.sha256:
            message = "Plan/source digest mismatch; create a newly bound plan with plan --from."
            raise PlanError(message, remedy=Remedy(RemedyAction.REBIND_PLAN))

    def as_dict(self) -> JsonObject:
        """Project the plan into the same tables used by its TOML file.

        Returns
        -------
        JsonObject
            The binding header, answered decision tables and fidelity policy.

        Raises
        ------
        PlanError
            A kind mixes incompatible document and target answer tables.

        """
        return record_dict(to_file(self))
