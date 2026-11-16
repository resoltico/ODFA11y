# SPDX-License-Identifier: AGPL-3.0-only
"""Raise source metadata findings from a typed read-only analysis."""

from odfa11y.concepts.metadata import DocumentMetadata, MetadataAnalysis
from odfa11y.report import Location, Report
from odfa11y.rules import registry as rules


def audit_metadata(analysis: MetadataAnalysis, report: Report) -> DocumentMetadata:
    metadata = analysis.metadata
    report.measure(metadata)
    problems = {}
    if analysis.metadata_problem:
        problems["metadata"] = analysis.metadata_problem
    if analysis.default_problem:
        problems["default_style"] = analysis.default_problem
    if problems:
        report.raise_(rules.META004, location=Location("meta/language"), details=problems)
    elif metadata.language is None:
        report.raise_(
            rules.META002,
            "Document language is not declared in metadata or the default style.",
            location=Location("meta/language"),
        )
    elif (
        analysis.declared_language
        and analysis.default_language
        and analysis.declared_language.casefold() != analysis.default_language.casefold()
    ):
        report.raise_(
            rules.META003,
            location=Location("meta/language"),
            details={"metadata": analysis.declared, "default_style": analysis.default},
        )
    if metadata.title is None:
        report.raise_(
            rules.META001, "Document title metadata is missing.", location=Location("meta/title")
        )
    return metadata
