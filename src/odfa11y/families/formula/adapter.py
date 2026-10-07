# SPDX-License-Identifier: MPL-2.0
"""Native MathML source semantics and the measured untagged Math PDF boundary."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from odfa11y.adapter import FamilyAdapter, ReviewItem
from odfa11y.odf import Family

from .audit import audit_formula
from .config import parse_table
from .expression import language, set_language, snapshot

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from odfa11y.report import Finding


def _preserved(before: tuple[str, ...], after: tuple[str, ...], removed: int) -> bool:
    return removed == 0 and before == after


def _template(by_remedy: Mapping[str, Sequence[Finding]]) -> list[str]:
    findings = by_remedy.get("formula.alternative", ())
    if not findings:
        return []
    return [
        "# [formula]",
        '# alternative = ""  # write the formula meaning in its language',
        f"# fingerprint = {json.dumps(findings[0].details.get('fingerprint', ''))}",
        "",
    ]


ADAPTER = FamilyAdapter(
    name="formula",
    family=Family.FORMULA,
    audit=audit_formula,
    default_language=language,
    set_default_language=set_language,
    snapshot=snapshot,
    preserved=_preserved,
    config_tables={"formula": parse_table},
    template=_template,
    review_items=(
        ReviewItem(
            "mathematics",
            "Whether the spoken alternative conveys every symbol, relation and grouping correctly.",
        ),
        ReviewItem("language", "Whether notation and spoken language match the intended audience."),
        ReviewItem(
            "export boundary",
            "Native Math export lacks PDF tagging; source correctness is not PDF/UA conformance.",
        ),
    ),
    pdf_filter="math_pdf_Export",
)
