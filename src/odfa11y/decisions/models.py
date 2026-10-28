# SPDX-License-Identifier: MPL-2.0
"""Registered human decisions, reviewed targets and their typed answers."""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, cast
from urllib.parse import quote, unquote

from odfa11y.errors import PlanError
from odfa11y.odf import Part

from .validation import validate_answer

if TYPE_CHECKING:
    from collections.abc import Mapping

    from odfa11y.odf import Family
    from odfa11y.report import Location

TARGET_FINGERPRINT_PATTERN = r"[0-9a-f]{16}"
ROOT_PARTS = frozenset(part.value for part in Part)
SEGMENT_PATTERN = (
    r"[A-Za-z][A-Za-z0-9_.-]*(?:\[(?:(?:name|id)="
    r"((?:[A-Za-z0-9_.~-]|%[0-9A-F]{2})*)|[1-9][0-9]*)\])?"
)
TARGET_SEGMENT = re.compile(SEGMENT_PATTERN + r"\Z")
TARGET_PATH_PATTERN = (
    r"^(?:"
    + "|".join(sorted(ROOT_PARTS))
    + ")/"
    + SEGMENT_PATTERN
    + "(?:/"
    + SEGMENT_PATTERN
    + r")*(?![\s\S])"
)


class DecisionScope(StrEnum):
    """Whether a human answer applies to a document or one reviewed target."""

    DOCUMENT = "document"
    TARGET = "target"


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
    target: Location | None
    fingerprint: str | None
    current: Mapping[str, object]
    rule_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Enforce one target grammar and mandatory targeted fingerprints."""
        _identity(self.kind, self.target, self.fingerprint)


@dataclass(frozen=True, slots=True)
class Decision:
    """An answered open decision, ready for family-specific operation translation."""

    kind: DecisionKind = field(metadata={"attribute": "id"})
    target: Location | None
    fingerprint: str | None
    answer: object

    def __post_init__(self) -> None:
        """Validate Python-created decisions with the same contract as parsed plans.

        Raises
        ------
        PlanError
            The answer belongs to another kind or violates its declared contract.

        """
        _identity(self.kind, self.target, self.fingerprint)
        if type(self.answer) is not self.kind.answer_type:
            msg = f"{self.kind.id} requires {self.kind.answer_type.__name__}"
            raise PlanError(msg)
        validate_answer(self.answer, self.kind.id)

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


def validate_target(path: str) -> None:
    """Require canonical logical paths, with encoded names/IDs and positive ordinals.

    Raises
    ------
    PlanError
        The path is not in the shared location grammar.

    """
    parts = path.split("/")
    if parts[0] not in ROOT_PARTS or not parts[1:]:
        msg = f"Invalid decision target: {path!r}"
        raise PlanError(msg)
    for segment in parts[1:]:
        match = TARGET_SEGMENT.fullmatch(segment)
        if match is None or (
            match[1] is not None and quote(unquote(match[1]), safe="") != match[1]
        ):
            msg = f"Decision target is not canonically encoded: {path!r}"
            raise PlanError(msg)


def _identity(kind: DecisionKind, target: Location | None, fingerprint: str | None) -> None:
    if kind.scope == DecisionScope.TARGET:
        if target is None or fingerprint is None:
            msg = f"{kind.id} requires a target and reviewed fingerprint"
            raise PlanError(msg)
        validate_target(target.path)
        if re.fullmatch(TARGET_FINGERPRINT_PATTERN, fingerprint) is None:
            msg = f"{kind.id} requires a 16-digit hexadecimal target fingerprint"
            raise PlanError(msg)
    elif target is not None or fingerprint is not None:
        msg = f"{kind.id} is document-scoped and bound through the plan source digest"
        raise PlanError(msg)
