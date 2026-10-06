# SPDX-License-Identifier: MPL-2.0
"""Models for ODF accessibility workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    """Classify audit findings by their effect on acceptance."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(slots=True, frozen=True)
class Issue:
    """Record a stable rule finding and its document location."""

    rule_id: str
    severity: Severity
    message: str
    location: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    fixable: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Serialize this record into JSON-compatible values.

        Returns
        -------
        dict[str, Any]
            A JSON-compatible record with severity values serialized as strings.

        """
        data = asdict(self)
        data["severity"] = self.severity.value
        return data


@dataclass(slots=True)
class AuditReport:
    """Collect findings and metadata for an audited artifact."""

    subject: str
    issues: list[Issue] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add(
        self,
        rule_id: str,
        severity: Severity,
        message: str,
        *,
        location: str | None = None,
        details: dict[str, Any] | None = None,
        fixable: bool = False,
    ) -> None:
        """Append a finding with its rule identifier and severity."""
        self.issues.append(
            Issue(
                rule_id=rule_id,
                severity=severity,
                message=message,
                location=location,
                details=details or {},
                fixable=fixable,
            )
        )

    @property
    def error_count(self) -> int:
        """The number of error findings."""
        return sum(i.severity is Severity.ERROR for i in self.issues)

    @property
    def warning_count(self) -> int:
        """The number of warning findings."""
        return sum(i.severity is Severity.WARNING for i in self.issues)

    @property
    def info_count(self) -> int:
        """The number of informational findings."""
        return sum(i.severity is Severity.INFO for i in self.issues)

    @property
    def passed(self) -> bool:
        """Whether the report contains no errors."""
        return self.error_count == 0

    def as_dict(self) -> dict[str, Any]:
        """Serialize this record into JSON-compatible values.

        Returns
        -------
        dict[str, Any]
            A JSON-compatible record with severity values serialized as strings.

        """
        return {
            "subject": self.subject,
            "passed": self.passed,
            "summary": {
                "errors": self.error_count,
                "warnings": self.warning_count,
                "info": self.info_count,
            },
            "metadata": self.metadata,
            "issues": [i.as_dict() for i in self.issues],
        }
