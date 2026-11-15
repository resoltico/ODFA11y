# SPDX-License-Identifier: MPL-2.0
"""The document policy kinds composed with every supported family."""

from odfa11y.decisions import DecisionKind, DecisionScope, OpenDecision
from odfa11y.decisions.answers import DocumentMetadataAnswer, OdfVersionAnswer
from odfa11y.remediate.metadata import edit_metadata
from odfa11y.remediate.version import edit_version
from odfa11y.report import FactKeys
from odfa11y.rules import registry as rules
lazy from odfa11y.report import Report
lazy from odfa11y.rules.registry import Rule

COMMON_KINDS = (
    DecisionKind(
        "document.odf_version",
        DecisionScope.DOCUMENT,
        OdfVersionAnswer,
        resolves=(
            rules.ODF001,
            rules.ODF003,
        ),
        edit=edit_version,
    ),
    DecisionKind(
        "document.metadata",
        DecisionScope.DOCUMENT,
        DocumentMetadataAnswer,
        resolves=(
            rules.META001,
            rules.META002,
            rules.META003,
            rules.CHART002,
            rules.CHART003,
        ),
        edit=edit_metadata,
    ),
)


def document_question(rule: Rule, report: Report) -> OpenDecision | None:
    """Create a common policy question as part of raising its motivating finding."""
    for kind in COMMON_KINDS:
        if rule not in kind.resolves:
            continue
        if kind.answer_type is DocumentMetadataAnswer:
            current = {
                "title": report.facts.get(FactKeys.DOCUMENT_TITLE),
                "description": report.facts.get(FactKeys.DOCUMENT_DESCRIPTION),
                "language": report.facts.get(FactKeys.DOCUMENT_LANGUAGE),
            }
        else:
            current = {"version": report.facts.get(FactKeys.DOCUMENT_ODF_VERSION)}
        return OpenDecision(kind, None, current)
    return None
