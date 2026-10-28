# SPDX-License-Identifier: MPL-2.0
"""Expose effective script-channel languages and safe target-specific review questions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.content import visible_words
from odfa11y.decisions import OpenDecision
from odfa11y.errors import RemediationError
from odfa11y.families.text.decisions import TARGET_LANGUAGE
from odfa11y.report import FactKeys, Location, rules

from .effective import CHANNELS, effective_languages, language_targets
from .operations import language_fingerprint

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument
    from odfa11y.report import Report


def audit_languages(document: OdfDocument, report: Report) -> None:
    """Resolve declarations without guessing a language from authored words."""
    rows: list[dict[str, object]] = []
    for target, node in language_targets(document).items():
        if not visible_words(node):
            continue
        location = Location(target)
        try:
            languages = effective_languages(document, node)
            fingerprint = language_fingerprint(document, node)
        except RemediationError as error:
            report.add(
                rules.LANG005,
                str(error),
                location=location,
                details={"native_editing": "Resolve the target's style inheritance in Writer."},
            )
            rows.append({"target": target, "reason": str(error)})
            continue
        current = dict(zip(CHANNELS, languages, strict=True))
        rows.append({"target": target, **current})
        if all(language is None for language in languages):
            report.add(rules.LANG004, location=location)
        report.add_decision(
            OpenDecision(TARGET_LANGUAGE, location, fingerprint, current, (rules.LANG004.id,))
        )
    report.facts[FactKeys.TEXT_EFFECTIVE_LANGUAGES] = rows
