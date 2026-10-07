# SPDX-License-Identifier: MPL-2.0
"""Render a commented configuration template from the decisions an audit leaves open."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from odfa11y.adapter import FamilyAdapter
    from odfa11y.report import Finding, Report

HEADER = (
    "# ODFA11y configuration template for {subject}\n"
    "# Generated from audit findings. Every line is commented out: uncomment and complete\n"
    "# only the decisions you have made. Nothing here changes a document until you do."
)
DOCUMENT_SETTINGS = (
    ("document.title", '""'),
    ("document.language", '"en-GB"'),
    ("document.odf_version", '"1.4"'),
)


def render_template(report: Report, adapter: FamilyAdapter) -> str:
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
    document = _document_lines(by_remedy)
    family = adapter.template(by_remedy)
    lines = [HEADER.format(subject=report.subject), ""]
    if document:
        lines += ["# [document]", *document, ""]
    lines += family
    if not document and not family:
        lines.append("# The audit found no decisions that a configuration can make.")
    return "\n".join(lines).rstrip() + "\n"


def _document_lines(by_remedy: dict[str, list[Finding]]) -> list[str]:
    lines = []
    for key, placeholder in DOCUMENT_SETTINGS:
        if key in by_remedy:
            setting = key.removeprefix("document.")
            lines.append(f"# {setting} = {placeholder}  # {by_remedy[key][0].rule_id}")
    return lines
