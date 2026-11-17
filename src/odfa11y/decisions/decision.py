# SPDX-License-Identifier: AGPL-3.0-only
"""Registered human decisions, reviewed targets and their typed answers."""

import dataclasses
from dataclasses import dataclass, field
from enum import StrEnum
lazy from collections.abc import Callable, Mapping

from odfa11y.contracts import JsonProperty, validate
from odfa11y.decisions.constraints import KindConstraints
from odfa11y.decisions.edit import EditResult
from odfa11y.errors import PlanError
from odfa11y.targets import Target, TargetPath
lazy from odfa11y.decisions.domain import TargetDomain
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.rules.registry import Rule


class DecisionScope(StrEnum):
    """Whether a human answer applies to a document or one reviewed target."""

    DOCUMENT = "document"
    TARGET = "target"

    @property
    def meaning(self) -> str:
        """Return the core-owned meaning of this value."""
        return {
            self.DOCUMENT: "The answer applies to the whole source bound by the plan digest.",
            self.TARGET: "The answer describes a specific content target bound by a fingerprint.",
        }[self]


@dataclass(frozen=True, slots=True)
class DecisionKind[A]:
    """One decision's identity, answer contract, applicability and executable operation."""

    id: str
    scope: DecisionScope
    _answer_type: type[A]
    edit: Callable[[OdfDocument, Decision[A]], EditResult]
    domain: TargetDomain | None = None
    resolves: tuple[Rule, ...] = ()
    constraints: KindConstraints = field(default_factory=KindConstraints)

    def __post_init__(self) -> None:
        """Require an introspectable answer contract.

        Raises
        ------
        PlanError
            The registered answer is not a dataclass.

        """
        if (self.scope is DecisionScope.TARGET) != (self.domain is not None):
            message = f"Decision {self.id!r} scope must agree with its target domain"
            raise PlanError(message)
        if not dataclasses.is_dataclass(self.answer_type):
            msg = f"Decision {self.id!r} needs an answer dataclass"
            raise PlanError(msg)

    @property
    def answer_type(self) -> type[A]:
        return self._answer_type


@dataclass(frozen=True, slots=True)
class QuestionContext:
    """The source element and nearby authored content needed to review a question."""

    element_kind: str
    excerpt: str | None = None
    name: str | None = None
    page: str | None = None
    sheet: str | None = None
    slide: str | None = None


@dataclass(frozen=True, slots=True)
class OpenDecision:
    """A reviewed identity and current values on which an audit requests human judgment."""

    _kind: DecisionKind
    target: Target | None
    current: Mapping[str, object]
    context: QuestionContext | None = None
    _rules: tuple[Rule, ...] = field(default=(), kw_only=True, repr=False)

    def __post_init__(self) -> None:
        """Enforce one target grammar and mandatory targeted fingerprints."""
        _identity(self.kind, self.target)

    @property
    def rules(self) -> tuple[Rule, ...]:
        return self._rules

    @JsonProperty
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(rule.id for rule in self._rules)

    @property
    def kind(self) -> DecisionKind:
        return self._kind

    @JsonProperty
    def kind_id(self) -> str:
        return self._kind.id


@dataclass(frozen=True, slots=True)
class Decision[A]:
    """An answered open decision, ready for family-specific operation translation."""

    _kind: DecisionKind[A]
    target: Target | None
    answer: A

    def __post_init__(self) -> None:
        """Validate Python-created decisions with the same contract as parsed plans.

        Raises
        ------
        PlanError
            The answer belongs to another kind or violates its declared contract.

        """
        _identity(self.kind, self.target)
        if type(self.answer) is not self.kind.answer_type:
            msg = f"{self.kind.id} requires {self.kind.answer_type.__name__}"
            raise PlanError(msg)
        validate(self.answer, self.kind.answer_type, label=self.kind.id, error=PlanError)

    @classmethod
    def _decoded(cls, kind: DecisionKind, target: Target | None, answer: object) -> Decision:
        _identity(kind, target)
        if type(answer) is not kind.answer_type:
            message = f"{kind.id} requires {kind.answer_type.__name__}"
            raise PlanError(message)
        result = object.__new__(cls)
        object.__setattr__(result, "_kind", kind)
        object.__setattr__(result, "target", target)
        object.__setattr__(result, "answer", answer)
        return result

    @property
    def target_path(self) -> TargetPath:
        """The required path of a targeted decision.

        Raises
        ------
        PlanError
            A document-scoped answer is consumed as a targeted one.

        """
        if self.target is None:
            msg = f"{self.kind.id} requires a target"
            raise PlanError(msg)
        return self.target.path

    @property
    def kind(self) -> DecisionKind[A]:
        return self._kind

    @JsonProperty
    def kind_id(self) -> str:
        return self._kind.id


def _identity(kind: DecisionKind, target: Target | None) -> None:
    if kind.scope == DecisionScope.TARGET and target is None:
        message = f"{kind.id} requires a target and reviewed fingerprint"
        raise PlanError(message)
    if kind.scope == DecisionScope.DOCUMENT and target is not None:
        message = f"{kind.id} is document-scoped and bound through the plan source digest"
        raise PlanError(message)
