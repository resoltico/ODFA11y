# SPDX-License-Identifier: AGPL-3.0-only
"""Expose effective script-channel languages and safe target-specific review questions."""

from dataclasses import dataclass, field
from typing import Annotated, Literal

from odfa11y.concepts import visible_words
from odfa11y.contracts import Description
from odfa11y.decisions import OpenDecision
from odfa11y.errors import DocumentRefusal
from odfa11y.families.text.domains import LANGUAGES
from odfa11y.families.text.kinds import TARGET_LANGUAGE
from odfa11y.families.text.language.effective import CHANNELS, effective_languages
from odfa11y.families.text.language.operations import language_fingerprint
from odfa11y.report import Location
from odfa11y.rules import registry as rules
from odfa11y.targets import Fingerprint, Target, TargetPath
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.report import Report


@dataclass(frozen=True, slots=True)
class MeasuredLanguages:
    target: TargetPath
    western: str | None
    asian: str | None
    complex: str | None
    state: Literal["measured"] = field(default="measured", init=False)


@dataclass(frozen=True, slots=True)
class UnresolvedLanguages:
    target: TargetPath
    reason: str
    state: Literal["unresolved"] = field(default="unresolved", init=False)


@dataclass(frozen=True, slots=True)
class LanguageMeasurements:
    """Measurements produced by text-language analysis; None denotes unmeasured data."""

    producer: Literal["text-language"] = field(default="text-language", init=False)
    effective_languages: Annotated[
        list[MeasuredLanguages | UnresolvedLanguages] | None,
        Description(
            "Per-target effective western, Asian and complex languages or refusal reasons."
        ),
    ] = None


def audit_languages(document: OdfDocument, report: Report) -> None:
    """Resolve declarations without guessing a language from authored words."""
    rows: list[MeasuredLanguages | UnresolvedLanguages] = []
    for target, node in LANGUAGES.enumerate(document):
        if not visible_words(node):
            continue
        location = Location(target)
        try:
            languages = effective_languages(document, node)
            fingerprint = language_fingerprint(document, node)
        except DocumentRefusal as error:
            report.raise_(
                rules.LANG002,
                str(error),
                location=location,
                details={"native_editing": "Resolve the target's style inheritance in Writer."},
            )
            rows.append(UnresolvedLanguages(target, str(error)))
            continue
        current = dict(zip(CHANNELS, languages, strict=True))
        rows.append(MeasuredLanguages(target, languages[0], languages[1], languages[2]))
        if all(language is None for language in languages):
            report.raise_(
                rules.LANG001,
                location=location,
                decision=OpenDecision(
                    TARGET_LANGUAGE,
                    Target((location).path, Fingerprint(fingerprint)),
                    current,
                ),
            )
    report.measure(LanguageMeasurements(effective_languages=rows))
