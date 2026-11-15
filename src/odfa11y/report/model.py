# SPDX-License-Identifier: MPL-2.0
"""Findings and the report container shared by every check."""

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Literal
lazy from collections.abc import Mapping
lazy from pathlib import Path

from odfa11y.errors import PackageError
from odfa11y.report.facts import FactSet
from odfa11y.rules.registry import Severity
from odfa11y.serialization import JsonProperty, record_dict
from odfa11y.targets import Location, TargetPath
lazy from odfa11y.decisions import OpenDecision
lazy from odfa11y.rules.registry import Rule
lazy from odfa11y.serialization import JsonObject

REPORT_SCHEMA_VERSION = 1


class ReportKind(StrEnum):
    """The subject and producer of a findings report."""

    ODF = "odf"
    PDF = "pdf"
    PDF_VALIDATION = "pdf-validation"
    FIDELITY = "fidelity"

    @property
    def meaning(self) -> str:
        return {
            self.ODF: "Findings about the OpenDocument source.",
            self.PDF: "Findings from built-in PDF inspection.",
            self.PDF_VALIDATION: "Findings from independent PDF/UA validation.",
            self.FIDELITY: "Findings about changes between source and candidate exports.",
        }[self]


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

    kind: ReportKind
    subject: str
    findings: list[Finding] = field(default_factory=list)
    facts: FactSet = field(default_factory=FactSet)
    _decisions: dict[tuple[str, TargetPath | None], OpenDecision] = field(
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
        key = (decision.kind.id, decision.target.path if decision.target else None)
        previous = self._decisions.get(key)
        if previous is not None:
            if previous.target != decision.target:
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
    def schema_version(self) -> Literal[1]:
        """The report's published schema version."""
        return REPORT_SCHEMA_VERSION

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
