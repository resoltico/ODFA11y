# SPDX-License-Identifier: MPL-2.0
"""Findings and the report container shared by every check."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Literal
from urllib.parse import quote
lazy from collections.abc import Mapping

from odfa11y.errors import PackageError
from odfa11y.serialization import JsonProperty, record_dict
lazy from odfa11y.decisions import OpenDecision

from .facts import FactSet
from .rules import Severity

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.serialization import JsonObject

    from .rules import Rule

REPORT_FORMAT = 6


@dataclass(frozen=True, slots=True)
class Location:
    """Where a finding applies, independent of how the document is stored.

    ``path`` is logical: a part of the document, optionally narrowed by ``/``-separated
    segments such as ``paragraph[3]``. ``member`` names the stored package member and is set
    only where that physical detail helps, for example for a package-level defect.
    """

    path: str
    member: str | None = None

    @classmethod
    def named(cls, part: str, element: str, name: str) -> Location:
        """Create an unambiguous named logical location.

        Returns
        -------
        Location
            A URI-escaped name within the given document part.

        """
        return cls(f"{part}/{element}[name={quote(name, safe='')}]")

    @classmethod
    def indexed(cls, part: str, element: str, index: int) -> Location:
        """Create an ordinal logical location.

        Returns
        -------
        Location
            A one-based element ordinal in its part.

        """
        return cls(f"{part}/{element}[{index}]")

    @property
    def label(self) -> str:
        """The path, followed by the member in parentheses when there is one."""
        return self.path if self.member is None else f"{self.path} ({self.member})"

    def as_dict(self) -> JsonObject:
        """Serialize the typed record.

        Returns
        -------
        JsonObject
            The published JSON fields.

        """
        return record_dict(self)


@dataclass(frozen=True, slots=True)
class Finding:
    """One observed condition, resolved from its rule at creation."""

    rule: Rule = field(metadata={"serialize": False})
    message: str
    location: Location | None = None
    details: Mapping[str, object] = field(default_factory=dict)

    @JsonProperty
    def rule_id(self) -> str:
        """The identity of the finding's authoritative rule."""
        return self.rule.id

    @JsonProperty
    def severity(self) -> Severity:
        """The rule's acceptance severity."""
        return self.rule.severity

    @JsonProperty
    def category(self) -> str:
        """The rule's concern category."""
        return self.rule.category.value

    def as_dict(self) -> JsonObject:
        """Serialize the typed record.

        Returns
        -------
        JsonObject
            The published JSON fields.

        """
        return record_dict(self)


@dataclass(frozen=True, slots=True)
class FindingCounts:
    """Counts of errors, warnings and information findings."""

    errors: int
    warnings: int
    info: int


@dataclass(slots=True)
class Report:
    """Collect findings and registered facts about one artifact or comparison."""

    kind: str
    subject: str
    findings: list[Finding] = field(default_factory=list)
    facts: FactSet = field(default_factory=FactSet)
    _decisions: dict[tuple[str, Location | None], OpenDecision] = field(
        default_factory=dict, init=False, repr=False, metadata={"serialize": False}
    )
    sources: tuple[Path, ...] = field(
        default=(), metadata={"serialize": False}
    )  # physical identity is internal and never serialized

    def add(
        self,
        rule: Rule,
        message: str | None = None,
        *,
        location: Location | None = None,
        details: Mapping[str, object] | None = None,
    ) -> None:
        """Append a finding for a rule, defaulting the message to the rule title."""
        self.findings.append(
            Finding(
                rule=rule,
                message=message or rule.title,
                location=location,
                details=record_dict(details) if details else {},
            )
        )

    @JsonProperty
    def decisions(self) -> tuple[OpenDecision, ...]:
        """The distinct reviewed questions this audit leaves open."""
        return tuple(self._decisions.values())

    def add_decision(self, decision: OpenDecision) -> None:
        """Collect one target once and retain every motivating rule.

        Raises
        ------
        PackageError
            An audit observes inconsistent identities for the same logical target.

        """
        key = (decision.kind.id, decision.target)
        previous = self._decisions.get(key)
        if previous is not None:
            if previous.fingerprint != decision.fingerprint:
                msg = "Document identity changed while collecting reviewed decisions"
                raise PackageError(msg)
            decision = replace(
                previous, rule_ids=tuple(dict.fromkeys((*previous.rule_ids, *decision.rule_ids)))
            )
        self._decisions[key] = decision

    @property
    def error_count(self) -> int:
        """The number of error findings."""
        return sum(f.severity is Severity.ERROR for f in self.findings)

    @property
    def warning_count(self) -> int:
        """The number of warning findings."""
        return sum(f.severity is Severity.WARNING for f in self.findings)

    @property
    def info_count(self) -> int:
        """The number of informational findings."""
        return sum(f.severity is Severity.INFO for f in self.findings)

    @JsonProperty
    def passed(self) -> bool:
        """Whether the report contains no errors."""
        return self.error_count == 0

    @JsonProperty
    def format(self) -> Literal[6]:
        """The report's published schema version."""
        return REPORT_FORMAT

    @JsonProperty
    def summary(self) -> FindingCounts:
        """Counts for the three registered finding severities."""
        return FindingCounts(self.error_count, self.warning_count, self.info_count)

    def as_dict(self) -> JsonObject:
        """Serialize the typed record.

        Returns
        -------
        JsonObject
            The published JSON fields.

        """
        return record_dict(self)
