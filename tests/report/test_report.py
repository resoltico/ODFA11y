# SPDX-License-Identifier: MPL-2.0
"""Rules, findings, rendering and exit statuses."""

from __future__ import annotations

import json
import re

import pytest

from odfa11y.decisions import OpenDecision
from odfa11y.errors import ReportError
from odfa11y.plans import registered_kinds
from odfa11y.report import (
    RULES,
    FactKeys,
    FactSet,
    Location,
    Report,
    Severity,
    exit_status,
    render_reports,
    rules,
)
from tests.fixtures.paths import REPOSITORY


def _report() -> Report:
    report = Report(
        kind="odf",
        subject="sample.odt",
        facts=FactSet({
            FactKeys.DOCUMENT_TITLE: "T",
            FactKeys.FIDELITY_RASTER_CHANGED_RATIOS: [0.0, 1.0],
        }),
    )
    report.add(
        rules.LINK001,
        "Needs review",
        location=Location("content/paragraph[2]"),
        details={"count": 2},
    )
    report.add_decision(
        OpenDecision(
            registered_kinds()["text.linkify_addresses"],
            None,
            None,
            {"enabled": False},
            ("LINK001",),
        )
    )
    return report


def test_text_report_shows_result_metadata_finding_and_decisions() -> None:
    lines = render_reports([_report()]).splitlines()
    assert lines[:3] == [
        "Subject: sample.odt (odf)",
        "Check: no errors",
        "Findings: 0 error(s), 1 warning(s), 0 info",
    ]
    assert "  document.title: T" in lines
    assert "  fidelity.raster_changed_ratios: 2 record(s)" in lines
    assert "  WARNING LINK001: Needs review" in lines
    assert "    location: content/paragraph[2]" in lines
    assert any("text.linkify_addresses" in line for line in lines)
    assert any(line.strip() == "count: 2" for line in lines)


def test_json_is_an_object_for_one_report_and_an_array_for_several() -> None:
    single = json.loads(render_reports([_report()], output_format="json"))
    assert single["format"] == 6
    assert single["kind"] == "odf"
    assert single["summary"] == {"errors": 0, "warnings": 1, "info": 0}
    finding = single["findings"][0]
    assert (finding["rule_id"], finding["severity"], finding["category"]) == (
        "LINK001",
        "warning",
        "links",
    )
    assert "remedy" not in finding
    assert single["decisions"][0]["kind"] == "text.linkify_addresses"
    assert finding["location"] == {"path": "content/paragraph[2]", "member": None}
    several = json.loads(render_reports([_report(), _report()], output_format="json"))
    assert isinstance(several, list)
    assert len(several) == 2


def test_unsupported_format_is_rejected() -> None:
    with pytest.raises(ReportError, match="Unsupported report format: yaml"):
        render_reports([_report()], output_format="yaml")


def test_message_defaults_to_the_rule_title() -> None:
    report = Report(kind="odf", subject="x")
    report.add(rules.META001)
    assert report.findings[0].message == rules.META001.title


@pytest.mark.parametrize(
    ("severity", "strict", "expected"),
    [
        (Severity.INFO, True, 0),
        (Severity.WARNING, False, 0),
        (Severity.WARNING, True, 1),
        (Severity.ERROR, False, 2),
        (Severity.ERROR, True, 2),
    ],
)
def test_exit_status_follows_highest_severity(
    severity: Severity, *, strict: bool, expected: int
) -> None:
    report = Report(kind="odf", subject="x")
    rule = next(r for r in RULES.values() if r.severity is severity)
    report.add(rule)
    assert exit_status([report], strict=strict) == expected


def test_exit_status_takes_the_worst_report() -> None:
    clean, warned, failed = (Report(kind="odf", subject=str(i)) for i in range(3))
    warned.add(rules.LINK001)
    failed.add(rules.META001)
    assert exit_status([clean, warned], strict=True) == 1
    assert exit_status([clean, warned, failed], strict=True) == 2
    assert exit_status([], strict=True) == 0


def test_registry_ids_severities_and_remedies_are_consistent() -> None:
    assert all(rule.id == key for key, rule in RULES.items())
    assert all(rule.title.endswith(".") for rule in RULES.values())
    assert all(re.fullmatch(r"[A-Z]+\d{3}", key) for key in RULES)


def test_rules_document_lists_exactly_the_registered_rules_with_severity_and_title() -> None:
    document = (REPOSITORY / "docs/RULES.md").read_text(encoding="utf-8")
    documented: dict[str, tuple[str, str, str]] = {}
    for line in document.splitlines():
        match = re.match(r"\| `([A-Z]+\d{3})` \| (Error|Warning|Info) \| (.+?) \| (.*?) \|", line)
        if match:
            documented[match.group(1)] = (
                match.group(2).lower(),
                match.group(3),
                match.group(4).replace("`", "").strip(),
            )
    assert documented == {
        key: (rule.severity.value, rule.title, ", ".join(rule.decision_kinds))
        for key, rule in RULES.items()
    }


def test_finding_references_one_rule_without_serializing_its_implementation() -> None:
    report = Report(kind="odf", subject="source.odt")
    report.add(rules.HEADING004, "A source-specific observation")
    [finding] = report.findings
    assert finding.rule is rules.HEADING004
    findings = report.as_dict()["findings"]
    assert isinstance(findings, list)
    [payload] = findings
    assert isinstance(payload, dict)
    assert payload["rule_id"] == "HEADING004"
    assert payload["severity"] == "info"
    assert payload["category"] == "semantics"
    assert payload["message"] == "A source-specific observation"
    assert "rule" not in payload
