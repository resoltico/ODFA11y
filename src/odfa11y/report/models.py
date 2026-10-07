# SPDX-License-Identifier: MPL-2.0
"""Findings and the report container shared by every check."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .rules import Severity

if TYPE_CHECKING:
    from .rules import Rule

REPORT_FORMAT = 1


@dataclass(frozen=True, slots=True)
class Finding:
    """One observed condition, resolved from its rule at creation."""

    rule_id: str
    severity: Severity
    category: str
    message: str
    location: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    remedy: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Serialize this finding into JSON-compatible values.

        Returns
        -------
        dict[str, Any]
            The finding with its severity as a string.

        """
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "category": self.category,
            "message": self.message,
            "location": self.location,
            "details": self.details,
            "remedy": self.remedy,
        }


@dataclass(slots=True)
class Report:
    """Collect findings and metadata about one artifact or comparison."""

    kind: str
    subject: str
    findings: list[Finding] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add(
        self,
        rule: Rule,
        message: str | None = None,
        *,
        location: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Append a finding for a rule, defaulting the message to the rule title."""
        self.findings.append(
            Finding(
                rule_id=rule.id,
                severity=rule.severity,
                category=rule.category.value,
                message=message or rule.title,
                location=location,
                details=details or {},
                remedy=rule.remedy,
            )
        )

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

    @property
    def passed(self) -> bool:
        """Whether the report contains no errors."""
        return self.error_count == 0

    def as_dict(self) -> dict[str, Any]:
        """Serialize this report into JSON-compatible values.

        Returns
        -------
        dict[str, Any]
            The versioned report record.

        """
        return {
            "format": REPORT_FORMAT,
            "kind": self.kind,
            "subject": self.subject,
            "passed": self.passed,
            "summary": {
                "errors": self.error_count,
                "warnings": self.warning_count,
                "info": self.info_count,
            },
            "metadata": self.metadata,
            "findings": [f.as_dict() for f in self.findings],
        }
