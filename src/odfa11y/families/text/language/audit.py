# SPDX-License-Identifier: MPL-2.0
"""Expose effective script-channel languages and safe target-specific review questions."""

from odfa11y.concepts import visible_words
from odfa11y.decisions import OpenDecision
from odfa11y.errors import DocumentRefusal
from odfa11y.families.text.kinds import TARGET_LANGUAGE
from odfa11y.families.text.language.effective import CHANNELS, effective_languages, language_targets
from odfa11y.families.text.language.operations import language_fingerprint
from odfa11y.report import FactKeys, Location
from odfa11y.rules import registry as rules
from odfa11y.targets import Fingerprint, Target
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.report import Report


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
        except DocumentRefusal as error:
            report.raise_(
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
            report.raise_(
                rules.LANG004,
                location=location,
                decision=OpenDecision(
                    TARGET_LANGUAGE,
                    Target((location).path, Fingerprint(fingerprint)),
                    current,
                ),
            )
    report.facts[FactKeys.TEXT_EFFECTIVE_LANGUAGES] = rows
