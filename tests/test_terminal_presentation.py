# SPDX-License-Identifier: MPL-2.0
"""Text reports prioritize actionable facts without changing machine payloads."""

import json

from odfa11y.report import FactKeys, FactSet, Location, Report, render_reports, rules, terminal_text


def test_terminal_fields_escape_controls_and_preserve_unicode() -> None:
    assert terminal_text("a\x1b[2J\r\n\t\x85\u202e\u2028b") == (
        "a\\x1b[2J\\x0d\\x0a\\x09\\x85\\u202e\\u2028b"
    )
    assert terminal_text("Rīga 👩\u200d💻") == "Rīga 👩\u200d💻"


def test_text_report_prioritizes_findings_and_wraps_without_breaking_tokens() -> None:
    report = Report(
        kind="odf", subject="sample.odt", facts=FactSet({FactKeys.DOCUMENT_TITLE: "Metadata"})
    )
    token = "https://example.test/" + "a" * 90
    report.add(
        rules.LINK001,
        "A long explanation " * 12,
        location=Location("paragraph[1]"),
        details={"address": token},
    )
    text = render_reports([report])
    assert "Check: no errors" in text
    assert text.index("WARNING LINK001") < text.index("Facts:")
    assert "location: paragraph[1]" in text
    assert token in text
    assert all(len(line) <= 80 for line in text.splitlines() if token not in line)


def test_controls_are_escaped_in_all_text_fields_and_retained_in_json() -> None:
    report = Report(
        kind="odf\x1b", subject="doc\n.odt", facts=FactSet({FactKeys.DOCUMENT_TITLE: "v\x85"})
    )
    report.add(rules.META001, "m\x1b", location=Location("p\u202e"), details={"d\t": "v\r"})
    text = render_reports([report])
    assert all(character not in text for character in ("\x1b", "\r", "\x85", "\u202e", "\t"))
    assert "\\x0a" in text
    assert "Check: errors found" in text
    payload = json.loads(render_reports([report], output_format="json"))
    assert payload["subject"] == "doc\n.odt"
    assert payload["findings"][0]["message"] == "m\x1b"
