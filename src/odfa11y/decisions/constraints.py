# SPDX-License-Identifier: AGPL-3.0-only
"""Typed kind constraints established against the complete plan before mutation."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum, auto

from odfa11y.decisions.answers import DocumentMetadataAnswer
from odfa11y.errors import DocumentRefusal
from odfa11y.odf import Family, Part
from odfa11y.odf import names as xml_names
lazy from odfa11y.decisions.decision import Decision
lazy from odfa11y.odf import OdfDocument


class RevisionPolicy(Enum):
    FORBID = auto()
    TITLE_DESCRIPTION = auto()

    @property
    def meaning(self) -> str:
        return {
            self.FORBID: "Tracked revisions must be absent for this edit.",
            self.TITLE_DESCRIPTION: "Only title and description may change with tracked revisions.",
        }[self]


class StructurePolicy(Enum):
    INDEPENDENT = auto()
    CHANGES = auto()
    STABLE = auto()
    STABLE_IF_ORDINAL = auto()

    @property
    def meaning(self) -> str:
        return {
            self.INDEPENDENT: "The edit does not require a stable ordinal structure.",
            self.CHANGES: "The edit can change structural target positions.",
            self.STABLE: "The edit requires a separate plan from structural edits.",
            self.STABLE_IF_ORDINAL: "An ordinal target cannot share a plan with structural edits.",
        }[self]


@dataclass(frozen=True, slots=True)
class KindConstraints:
    revisions: RevisionPolicy = RevisionPolicy.FORBID
    structure: StructurePolicy = StructurePolicy.INDEPENDENT
    checks: tuple[Callable[[OdfDocument, Decision, Sequence[Decision]], None], ...] = ()


def check_plan(document: OdfDocument, decisions: Sequence[Decision]) -> None:
    changes_structure = any(
        decision.kind.constraints.structure is StructurePolicy.CHANGES for decision in decisions
    )
    revisions = (
        document.kind is not None
        and document.kind.family is Family.TEXT
        and any(node.tag in REVISION_TAGS for node in document.tree(Part.CONTENT).iter())
    )
    for decision in decisions:
        if revisions and not _revision_allowed(decision):
            message = (
                "Tracked revisions permit only title/description metadata edits; "
                "nothing was written."
            )
            raise DocumentRefusal(message)
        if changes_structure and _needs_stable_structure(decision):
            message = "Ordinal targets require a separate reviewed structural plan."
            raise DocumentRefusal(message)


REVISION_TAGS = frozenset({
    xml_names.TEXT_TRACKED_CHANGES,
    xml_names.TEXT_CHANGE,
    xml_names.TEXT_CHANGE_START,
    xml_names.TEXT_CHANGE_END,
})


def _revision_allowed(decision: Decision) -> bool:
    return (
        decision.kind.constraints.revisions is RevisionPolicy.TITLE_DESCRIPTION
        and isinstance(decision.answer, DocumentMetadataAnswer)
        and decision.answer.language is None
    )


def _needs_stable_structure(decision: Decision) -> bool:
    structure = decision.kind.constraints.structure
    return structure is StructurePolicy.STABLE or (
        structure is StructurePolicy.STABLE_IF_ORDINAL
        and decision.target is not None
        and "[id=" not in decision.target.path
    )
