# SPDX-License-Identifier: MPL-2.0
"""Reviewable [presentation] decisions, all disabled until a person selects them."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from odfa11y.report import Finding


def template(by_remedy: Mapping[str, Sequence[Finding]]) -> list[str]:
    """Print each target once with its reviewed fingerprint.

    Returns
    -------
    list[str]
        Commented TOML lines.

    """
    lines = []
    seen = set()
    for finding in by_remedy.get("presentation.pages", ()):
        name = finding.details.get("page")
        if not name or name in seen:
            continue
        seen.add(name)
        lines += [
            f"# [presentation.pages.{json.dumps(name)}]",
            '# title = ""  # choose the page title',
            '# description = ""  # describe the page purpose',
            f"# fingerprint = {json.dumps(finding.details.get('fingerprint', ''))}",
        ]
        identities = finding.details.get("shape_identities", [])
        if identities and all(isinstance(identity, str) for identity in identities):
            lines.append(f"# navigation = {json.dumps(identities)}  # review the complete order")
        else:
            lines.append("# Set native navigation first when shape identities are missing.")
        lines.append("")
    seen.clear()
    for finding in by_remedy.get("presentation.graphics", ()):
        selector = finding.details.get("selector")
        if not selector or selector in seen:
            continue
        seen.add(selector)
        lines += [
            f"# [presentation.graphics.{json.dumps(selector)}]",
            '# title = ""',
            '# description = ""  # describe the graphic in context',
            f"# fingerprint = {json.dumps(finding.details.get('fingerprint', ''))}",
            "",
        ]
    return lines
