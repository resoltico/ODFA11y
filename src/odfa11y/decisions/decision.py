# SPDX-License-Identifier: MPL-2.0
"""Registered human decisions, reviewed targets and their typed answers."""

import dataclasses
from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast
lazy from collections.abc import Mapping

from odfa11y.decisions.validation import validate_answer
from odfa11y.errors import PlanError
from odfa11y.targets import Target
lazy from odfa11y.odf import Family


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
class DecisionKind:
    """One decision's identity, answer contract, applicability and executable operation."""

    id: str
    scope: DecisionScope
    answer_type: type[object] = field(metadata={"serialize": False})
    families: frozenset[Family]
    operation: str

    def __post_init__(self) -> None:
        """Require an introspectable answer contract.

        Raises
        ------
        PlanError
            The registered answer is not a dataclass.

        """
        if not dataclasses.is_dataclass(self.answer_type):
            msg = f"Decision {self.id!r} needs an answer dataclass"
            raise PlanError(msg)


@dataclass(frozen=True, slots=True)
class OpenDecision:
    """A reviewed identity and current values on which an audit requests human judgment."""

    kind: DecisionKind = field(metadata={"attribute": "id"})
    target: Target | None
    current: Mapping[str, object]
    rule_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Enforce one target grammar and mandatory targeted fingerprints."""
        _identity(self.kind, self.target)


@dataclass(frozen=True, slots=True)
class Decision:
    """An answered open decision, ready for family-specific operation translation."""

    kind: DecisionKind = field(metadata={"attribute": "id"})
    target: Target | None
    answer: object

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
        validate_answer(self.answer, self.kind.id)

    @property
    def target_path(self) -> str:
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

    def answer_as[T](self, expected: type[T]) -> T:
        """Read an answer through its family's declared type.

        Returns
        -------
        T
            The validated answer.

        Raises
        ------
        PlanError
            A family attempts to consume another answer type.

        """
        if type(self.answer) is not expected:
            msg = f"{self.kind.id} cannot provide {expected.__name__}"
            raise PlanError(msg)
        return cast("T", self.answer)


def _identity(kind: DecisionKind, target: Target | None) -> None:
    if kind.scope == DecisionScope.TARGET and target is None:
        message = f"{kind.id} requires a target and reviewed fingerprint"
        raise PlanError(message)
    if kind.scope == DecisionScope.DOCUMENT and target is not None:
        message = f"{kind.id} is document-scoped and bound through the plan source digest"
        raise PlanError(message)
