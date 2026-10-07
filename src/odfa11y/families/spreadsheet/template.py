# SPDX-License-Identifier: MPL-2.0
"""Commented ``[spreadsheet]`` configuration lines for the decisions an audit leaves open."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from odfa11y.report import Finding


def spreadsheet_template(by_remedy: Mapping[str, Sequence[Finding]]) -> list[str]:
    """Build the commented lines for every spreadsheet finding that has a remedy.

    Returns
    -------
    list[str]
        TOML lines with every setting commented out; empty when nothing applies.

    """
    return [
        *_sheet_names(by_remedy.get("spreadsheet.sheet_names", ())),
        *_alt_text(by_remedy.get("spreadsheet.graphics", ())),
    ]


def _sheet_names(findings: Sequence[Finding]) -> list[str]:
    names = sorted({str(name) for finding in findings if (name := finding.details.get("sheet"))})
    if not names:
        return []
    return [
        "# [spreadsheet.sheet_names]",
        *(
            f'# {json.dumps(name)} = ""  # {findings[0].rule_id}: say what the sheet holds'
            for name in names
        ),
        "",
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
            f"# [spreadsheet.graphics.{json.dumps(str(key))}]",
            '# title = ""',
            f'# description = ""  # {finding.rule_id}: describe what the object conveys',
            (
                f"# fingerprint = {json.dumps(finding.details.get('fingerprint', ''))}"
                "  # binds this entry to the object you reviewed"
            ),
            "",
        ]
    return lines
