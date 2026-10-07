# SPDX-License-Identifier: MPL-2.0
"""Render a commented configuration template from the decisions an audit leaves open."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from odfa11y.report import Finding, Report

HEADER = (
    "# ODFA11y configuration template for {subject}\n"
    "# Generated from audit findings. Every line is commented out: uncomment and complete\n"
    "# only the decisions you have made. Nothing here changes a document until you do."
)


def render_template(report: Report) -> str:
    """Build a commented starter configuration covering the findings that have a remedy.

    Returns
    -------
    str
        TOML text in which every setting is commented out.

    """
    by_remedy: dict[str, list[Finding]] = {}
    for finding in report.findings:
        if finding.remedy:
            by_remedy.setdefault(finding.remedy, []).append(finding)
    sections = [
        ("[document]", _document_lines(by_remedy)),
        ("[remediation]", _remediation_lines(by_remedy)),
        ("[table_headers]", _table_lines(by_remedy.get("table_headers", []))),
    ]
    lines = [HEADER.format(subject=report.subject), ""]
    for title, body in sections:
        if body:
            lines += [title, *body, ""]
    graphics = _alt_text_lines(by_remedy.get("alt_text", []))
    lines += graphics
    if not graphics and not any(body for _title, body in sections):
        lines.append("# The audit found no decisions that a configuration can make.")
    return "\n".join(lines).rstrip() + "\n"


def _document_lines(by_remedy: dict[str, list[Finding]]) -> list[str]:
    lines = []
    for key, placeholder in (
        ("document.title", '""'),
        ("document.language", '"en-GB"'),
        ("document.odf_version", '"1.4"'),
    ):
        if key in by_remedy:
            setting = key.removeprefix("document.")
            lines.append(f"# {setting} = {placeholder}  # {by_remedy[key][0].rule_id}")
    return lines


def _remediation_lines(by_remedy: dict[str, list[Finding]]) -> list[str]:
    lines = []
    for key in ("remediation.linkify_plain_addresses", "remediation.remove_empty_spacers"):
        if key in by_remedy:
            setting = key.removeprefix("remediation.")
            lines.append(
                f"# {setting} = true  # {by_remedy[key][0].rule_id}; review before enabling"
            )
    return lines


def _table_lines(findings: list[Finding]) -> list[str]:
    names = sorted({str(f.details["table"]) for f in findings if f.details.get("table")})
    return [
        f"# {json.dumps(name)} = 1  # rows that are headers; check the table first"
        for name in names
    ]


def _alt_text_lines(findings: list[Finding]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for finding in findings:
        key = finding.details.get("frame") or finding.details.get("href")
        if not key or key in seen:
            continue
        seen.add(str(key))
        lines += [
            f"# [alt_text.{json.dumps(str(key))}]",
            '# title = ""',
            f'# description = ""  # {finding.rule_id}: describe what the graphic conveys',
            "",
        ]
    return lines
