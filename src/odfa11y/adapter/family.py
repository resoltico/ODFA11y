# SPDX-License-Identifier: MPL-2.0
"""What a document family contributes: audit rules, operations, meaning-specific hooks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

from odfa11y.errors import PlanError
lazy from odfa11y.outcomes import ReviewTopic

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from odfa11y.decisions import Decision, DecisionKind
    from odfa11y.native.probes import CapabilityProbe
    from odfa11y.odf import Family, OdfDocument
    from odfa11y.report import Report

    from .operation import Operation, Outcome


@dataclass(frozen=True, slots=True)
class ReviewItem:
    """A judgement a person still has to make after the machine checks."""

    key: ReviewTopic
    text: str


class StyleUsage(TypedDict):
    """A style's usage count, parent and effective spacing in an adapter report."""

    style: str
    count: int
    parent: str | None
    spacing: dict[str, str]


@dataclass(frozen=True, slots=True)
class PreservationSnapshot:
    """The family's immutable protected-content representation."""

    content: tuple[str, ...]


class FamilyAdapter(ABC):
    """Required family semantics and explicit defaults for optional capabilities."""

    name: str
    family: Family | None
    review_items: tuple[ReviewItem, ...] = ()
    decision_kinds: tuple[DecisionKind, ...] = ()
    pdf_filter: str | None = None
    probes: tuple[CapabilityProbe, ...] = ()

    @abstractmethod
    def audit(self, document: OdfDocument, report: Report) -> None:
        """Inspect the family's source semantics without mutation."""

    @staticmethod
    def default_language(document: OdfDocument) -> str | None:
        """Read the default language when the family has such a target.

        Returns
        -------
        str | None
            The declared language, or None when no default-style target exists.

        """
        del document
        return None

    @staticmethod
    def set_default_language(document: OdfDocument, tag: str) -> bool:
        """Set a supported default-language target.

        Returns
        -------
        bool
            Whether a family-specific style changed.

        """
        del document, tag
        return False

    @abstractmethod
    def snapshot(self, document: OdfDocument) -> PreservationSnapshot:
        """Capture the family's protected meaning.

        Returns
        -------
        PreservationSnapshot
            Family-owned protected content facts.

        """

    @staticmethod
    def preserved(
        before: PreservationSnapshot, after: PreservationSnapshot, outcomes: Sequence[Outcome]
    ) -> bool:
        """Compare protected content; families may interpret their own typed outcomes.

        Returns
        -------
        bool
            Whether protected meaning survived every operation.

        """
        del outcomes
        return before == after

    def operations(
        self, document: OdfDocument, decisions: Sequence[Decision]
    ) -> tuple[Operation, ...]:
        """Translate supported human answers into executable changes.

        Returns
        -------
        tuple[Operation, ...]
            No family operations for adapters supporting only common document answers.

        Raises
        ------
        PlanError
            A family answer has no implementation.

        """
        del document
        if decisions:
            msg = f"No decision operation implementation for {self.name}"
            raise PlanError(msg)
        return ()

    @staticmethod
    def preflight(document: OdfDocument, operations: Sequence[Operation]) -> None:
        """Establish additional family constraints before any edit."""
        del document, operations

    @staticmethod
    def protect_edit(document: OdfDocument, operation: Operation) -> Callable[[], bool] | None:
        """Establish operation-specific protected facts.

        Returns
        -------
        Callable[[], bool] | None
            A post-edit guard, or None when the family needs only its whole-run snapshot.

        """
        del document, operation
        return None
