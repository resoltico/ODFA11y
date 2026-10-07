# SPDX-License-Identifier: MPL-2.0
"""Render privacy-preserving SARIF using explicit physical source identities."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, unquote

from .rules import RULES, Severity

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from .models import Finding, Report

SCHEMA_URI = "https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/schemas/sarif-schema-2.1.0.json"
_LEVELS = {Severity.ERROR: "error", Severity.WARNING: "warning", Severity.INFO: "note"}
_UNSAFE_LABEL = re.compile(
    r"(?:[a-z][a-z0-9+.-]*://[^/\s]*@|(?:/Users/|/home/|[A-Za-z]:[\\/]))", re.IGNORECASE
)


def sarif_log(reports: Iterable[Report], *, source_root: Path) -> dict[str, Any]:
    """Build a SARIF log with root-relative artifacts and registered finding rules.

    Free-form messages, display subjects and metadata are intentionally excluded: they
    may contain source content, credentials or local paths. Logical locations are kept;
    filesystem locations never invent line numbers for document elements.

    Returns
    -------
    dict[str, Any]
        A SARIF 2.1.0 log suitable for JSON serialization.

    Raises
    ------
    ValueError
        A source is missing, outside the root, or a finding has unsafe identity data.

    """
    root = _resolved(source_root)
    if not root.is_dir():
        msg = "SARIF source root must be an existing directory."
        raise ValueError(msg)
    items = list(reports)
    artifacts: dict[Path, int] = {}
    source_indices: dict[Path, int] = {}
    artifact_records: list[dict[str, Any]] = []
    for report in items:
        if not report.sources:
            msg = "SARIF requires explicit source identities for every report."
            raise ValueError(msg)
        for source in report.sources:
            if source in source_indices:
                continue
            resolved = _resolved(source)
            if not resolved.is_file() or not resolved.is_relative_to(root):
                msg = "SARIF source must be a file within the source root."
                raise ValueError(msg)
            if resolved not in artifacts:
                artifacts[resolved] = len(artifacts)
                uri = quote(resolved.relative_to(root).as_posix(), safe="/")
                artifact_records.append({"location": {"uri": uri}})
            source_indices[source] = artifacts[resolved]
    ids = sorted({finding.rule_id for report in items for finding in report.findings})
    if any(rule_id not in RULES for rule_id in ids):
        msg = "SARIF findings must reference registered rules."
        raise ValueError(msg)
    descriptors = [_descriptor(rule_id) for rule_id in ids]
    rule_indices = {rule_id: index for index, rule_id in enumerate(ids)}
    results = [
        _result(finding, report, rule_indices[finding.rule_id], source_indices)
        for report in items
        for finding in report.findings
    ]
    return {
        "$schema": SCHEMA_URI,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "ODFA11y", "rules": descriptors}},
                "artifacts": artifact_records,
                "results": results,
            }
        ],
    }


def _descriptor(rule_id: str) -> dict[str, Any]:
    rule = RULES[rule_id]
    result: dict[str, Any] = {
        "id": rule.id,
        "shortDescription": {"text": rule.title},
        "defaultConfiguration": {"level": _LEVELS[rule.severity]},
        "properties": {"category": rule.category.value},
    }
    if rule.remedy:
        result["help"] = {"text": f"Remedy configuration: {rule.remedy}"}
    return result


def _result(
    finding: Finding, report: Report, rule_index: int, artifacts: dict[Path, int]
) -> dict[str, Any]:
    rule = RULES[finding.rule_id]
    locations = []
    for source in report.sources:
        location: dict[str, Any] = {
            "physicalLocation": {"artifactLocation": {"index": artifacts[source]}},
        }
        if finding.location:
            _safe_label(finding.location.path)
            location["logicalLocations"] = [{"fullyQualifiedName": finding.location.path}]
            if finding.location.member:
                _safe_label(finding.location.member)
                location["properties"] = {"packageMember": finding.location.member}
        locations.append(location)
    result: dict[str, Any] = {
        "ruleId": rule.id,
        "ruleIndex": rule_index,
        "level": _LEVELS[finding.severity],
        "message": {"text": rule.title},
        "locations": locations,
        "properties": {"category": rule.category.value},
    }
    if rule.remedy:
        result["properties"]["remedy"] = rule.remedy
    return result


def _safe_label(value: str) -> None:
    decoded = unquote(value)
    if (
        _UNSAFE_LABEL.search(decoded)
        or decoded.startswith(("/", "\\"))
        or re.search(r"[=\s](?:/|[A-Za-z]:[\\/])", decoded)
    ):
        msg = "SARIF logical location contains unsafe path or credential information."
        raise ValueError(msg)


def _resolved(source: Path) -> Path:
    try:
        return source.resolve(strict=True)
    except OSError:
        msg = "SARIF source identity cannot be resolved."
        raise ValueError(msg) from None
