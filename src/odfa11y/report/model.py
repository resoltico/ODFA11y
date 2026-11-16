# SPDX-License-Identifier: MPL-2.0
"""Findings and the report container shared by every check."""

from dataclasses import dataclass, field, fields, is_dataclass, replace
from enum import StrEnum
from typing import Literal
lazy from collections.abc import Callable, Mapping
lazy from pathlib import Path

from odfa11y.contracts import JsonProperty, record_dict, validate
from odfa11y.decisions.decision import QuestionContext
from odfa11y.errors import InvalidOption, PackageError
from odfa11y.rules.details import bounded_details
from odfa11y.rules.registry import Severity
from odfa11y.targets import Location, TargetPath
lazy from odfa11y.concepts.review import ReviewTopic
lazy from odfa11y.contracts import JsonObject
lazy from odfa11y.decisions import OpenDecision
lazy from odfa11y.rules.registry import Rule

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

    _rule: Rule
    message: str
    location: Location | None = None
    details: Mapping[str, object] = field(default_factory=dict)
    _decision: OpenDecision | None = field(default=None, repr=False)

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
        return self.rule.category

    def as_dict(self) -> JsonObject:
        """Serialize the typed record.

        Returns
        -------
        JsonObject
            The published JSON fields.

        """
        return record_dict(self)

    @property
    def rule(self) -> Rule:
        return self._rule


@dataclass(frozen=True, slots=True)
class FindingCounts:
    """Counts of errors, warnings and information findings."""

    errors: int
    warnings: int
    info: int


@dataclass(slots=True)
class Report[F = object]:
    """Collect findings and registered facts about one artifact or comparison."""

    kind: ReportKind
    subject: str
    findings: list[Finding] = field(default_factory=list)
    facts: tuple[F, ...] = ()
    review_topics: tuple[ReviewTopic, ...] = ()
    _sources: tuple[Path, ...] = field(default=())
    _question_for: Callable[[Rule], OpenDecision | None] | None = field(default=None, repr=False)

    def measure(self, record: F) -> None:
        """Retain producer-owned typed measurements, merging measured fragment fields."""
        if not is_dataclass(record) or isinstance(record, type):
            message = "Report measurements must be dataclass values"
            raise TypeError(message)
        validate(record)
        records = list(self.facts)
        for index, previous in enumerate(records):
            if (
                is_dataclass(previous)
                and not isinstance(previous, type)
                and type(previous) is type(record)
            ):
                updates = {
                    item.name: getattr(record, item.name)
                    for item in fields(record)
                    if item.init and getattr(record, item.name) is not None
                }
                records[index] = replace(previous, **updates)
                break
        else:
            records.append(record)
        self.facts = tuple(records)

    def raise_(
        self,
        rule: Rule,
        message: str | None = None,
        *,
        location: Location | None = None,
        details: Mapping[str, object] | None = None,
        decision: OpenDecision | None = None,
    ) -> None:
        """Append a finding for a rule, defaulting the message to the rule title."""
        if decision is None and self._question_for is not None:
            decision = self._question_for(rule)
        if decision is not None and rule not in decision.kind.resolves:
            message = f"Decision {decision.kind.id!r} does not address rule {rule.id}"
            raise ValueError(message)
        if decision is not None and decision.context is None:
            path = (
                decision.target.path
                if decision.target
                else location.path
                if location
                else "document"
            )
            element_kind = path.rsplit("/", 1)[-1].split("[", 1)[0]
            values = details or {}
            excerpt = values.get("text")
            name = next(
                (values[key] for key in ("frame", "table", "page", "sheet") if values.get(key)),
                None,
            )
            decision = replace(
                decision,
                context=QuestionContext(
                    element_kind,
                    str(excerpt) if excerpt else None,
                    str(name) if name else None,
                    sheet=str(values["sheet"]) if values.get("sheet") else None,
                ),
            )
        detail_values = bounded_details(details or {})
        try:
            validate(detail_values, rule.details, label=f"{rule.id} details")
        except InvalidOption as error:
            raise ValueError(str(error)) from error
        self.findings.append(
            Finding(
                _rule=rule,
                _decision=decision,
                message=message or rule.title,
                location=location,
                details=detail_values,
            )
        )

    @JsonProperty
    def decisions(self) -> tuple[OpenDecision, ...]:
        """The distinct reviewed questions this audit leaves open."""
        decisions: dict[tuple[str, TargetPath | None], OpenDecision] = {}
        for finding in self.findings:
            decision = finding._decision
            if decision is None:
                continue
            key = (decision.kind.id, decision.target.path if decision.target else None)
            previous = decisions.get(key)
            if previous is not None and previous.target != decision.target:
                message = "Document identity changed while collecting reviewed decisions"
                raise PackageError(message)
            rules = previous.rules if previous is not None else ()
            decisions[key] = replace(
                previous or decision, _rules=tuple(dict.fromkeys((*rules, finding.rule)))
            )
        return tuple(decisions.values())

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

    @property
    def sources(self) -> tuple[Path, ...]:
        return self._sources

    @sources.setter
    def sources(self, value: tuple[Path, ...]) -> None:
        self._sources = value
