# SPDX-License-Identifier: MPL-2.0
"""Commented ``[text]`` configuration lines for the decisions a text audit leaves open."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from odfa11y.report import Finding


def text_template(by_remedy: Mapping[str, Sequence[Finding]]) -> list[str]:
    """Build the commented lines for every text finding that has a remedy.

    Returns
    -------
    list[str]
        TOML lines with every setting commented out; empty when nothing applies.

    """
    lines: list[str] = []
    for title, body in (
        ("[text.remediation]", _remediation(by_remedy)),
        ("[text.table_headers]", _tables(by_remedy.get("text.table_headers", ()))),
    ):
        if body:
            lines += [f"# {title}", *body, ""]
    lines += _alt_text(by_remedy.get("text.alt_text", ()))
    return lines


def _remediation(by_remedy: Mapping[str, Sequence[Finding]]) -> list[str]:
    lines = []
    for key in (
        "text.remediation.linkify_plain_addresses",
        "text.remediation.remove_empty_spacers",
    ):
        if key in by_remedy:
            setting = key.rpartition(".")[2]
            lines.append(
                f"# {setting} = true  # {by_remedy[key][0].rule_id}; review before enabling"
            )
    return lines


def _tables(findings: Sequence[Finding]) -> list[str]:
    seen: dict[str, str] = {}
    for finding in findings:
        name = finding.details.get("table")
        if name:
            seen.setdefault(str(name), str(finding.details.get("fingerprint", "")))
    return [
        (
            f"# {json.dumps(name)} = {{ rows = 1, fingerprint = {json.dumps(fingerprint)} }}"
            "  # rows that are headers; check the table first"
        )
        for name, fingerprint in sorted(seen.items())
    ]


def _alt_text(findings: Sequence[Finding]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for finding in findings:
        key = finding.details.get("frame") or finding.details.get("href")
        if not key or key in seen:
            continue
        seen.add(str(key))
        lines += [
            f"# [text.alt_text.{json.dumps(str(key))}]",
            '# title = ""',
            f'# description = ""  # {finding.rule_id}: describe what the graphic conveys',
            (
                f"# fingerprint = {json.dumps(finding.details.get('fingerprint', ''))}"
                "  # binds this entry to the graphic you reviewed"
            ),
            "",
        ]
    return lines
