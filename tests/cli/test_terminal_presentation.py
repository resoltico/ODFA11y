# SPDX-License-Identifier: AGPL-3.0-only
"""Text reports prioritize actionable facts without changing machine payloads."""

import json

from odfa11y import render_json
from odfa11y.cli.text import render_reports, terminal_text
from odfa11y.concepts.metadata import DocumentMetadata
from odfa11y.report import Location, Report
from odfa11y.report.model import ReportKind
from odfa11y.rules import registry as rules
from tests.report.test_report import _report


def test_terminal_fields_escape_controls_and_preserve_unicode() -> None:
    assert terminal_text("a\x1b[2J\r\n\t\x85\u202e\u2028b") == (
        "a\\x1b[2J\\x0d\\x0a\\x09\\x85\\u202e\\u2028b"
    )
    assert terminal_text("Rīga 👩\u200d💻") == "Rīga 👩\u200d💻"


def test_text_report_prioritizes_findings_and_wraps_without_breaking_tokens() -> None:
    report = Report[object](
        kind=ReportKind.ODF,
        subject="sample.odt",
        facts=(DocumentMetadata(title="Metadata"),),
    )
    token = "https://example.test/" + "a" * 90
    report.raise_(
        rules.LINK001,
        "A long explanation " * 12,
        location=Location("content/paragraph[1]"),
        details={"text": token},
    )
    text = render_reports([report])
    assert "Findings: 0 error(s)" in text
    assert text.index(f"WARNING {rules.LINK001.id}") < text.index("Facts:")
    assert "location: content/paragraph[1]" in text
    assert token in text
    assert all(len(line) <= 80 for line in text.splitlines() if token not in line)


def test_controls_are_escaped_in_all_text_fields_and_retained_in_json() -> None:
    report = Report[object](
        kind=ReportKind.ODF, subject="doc\n.odt", facts=(DocumentMetadata(title="v\x85"),)
    )
    report.raise_(
        rules.LINK001,
        "m\x1b",
        location=Location.named("content", "paragraph", "p\u202e"),
        details={"text": "v\r"},
    )
    text = render_reports([report])
    assert all(character not in text for character in ("\x1b", "\r", "\x85", "\u202e", "\t"))
    assert "\\x0a" in text
    assert "Findings: 0 error(s)" in text
    payload = json.loads(render_json(report))
    assert payload["subject"] == "doc\n.odt"
    assert payload["findings"][0]["message"] == "m\x1b"


def test_text_report_shows_result_metadata_finding_and_decisions() -> None:
    lines = render_reports([_report()]).splitlines()
    assert lines[:2] == [
        "Subject: sample.odt (odf)",
        "Findings: 0 error(s), 1 warning(s), 0 info",
    ]
    assert "  odf-metadata.title: T" in lines
    assert "  pdf-fidelity.raster_changed_ratios: 2 record(s)" in lines
    assert f"  WARNING {rules.LINK001.id}: Needs review" in lines
    assert "    location: content/paragraph[2]" in lines
    assert any("text.linkify_addresses" in line for line in lines)
    assert any(line.strip() == "text: Two addresses" for line in lines)
