# SPDX-License-Identifier: MPL-2.0
"""The document policy kinds composed with every supported family."""

from odfa11y.concepts.metadata import DocumentMetadata
from odfa11y.decisions import DecisionKind, DecisionScope, OpenDecision
from odfa11y.decisions.answers import DocumentMetadataAnswer, OdfVersionAnswer
from odfa11y.remediate.metadata import edit_metadata
from odfa11y.remediate.version import edit_version
from odfa11y.rules import registry as rules
lazy from odfa11y.rules.registry import Rule

COMMON_KINDS = (
    DecisionKind(
        "document.odf_version",
        DecisionScope.DOCUMENT,
        OdfVersionAnswer,
        resolves=(
            rules.ODF001,
            rules.ODF003,
            rules.ODF004,
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
            rules.CHART003,
            rules.CHART004,
        ),
        edit=edit_metadata,
    ),
)


def document_question(
    rule: Rule, *, metadata: DocumentMetadata, version: str | None
) -> OpenDecision | None:
    """Create a common policy question as part of raising its motivating finding."""
    for kind in COMMON_KINDS:
        if rule not in kind.resolves:
            continue
        if kind.answer_type is DocumentMetadataAnswer:
            current = {
                "title": metadata.title,
                "description": metadata.description,
                "language": metadata.language,
            }
        else:
            current = {"version": version}
        return OpenDecision(kind, None, current)
    return None
