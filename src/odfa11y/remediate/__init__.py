# SPDX-License-Identifier: MPL-2.0
"""Guarded in-memory candidates and typed remediation evidence."""

lazy from odfa11y.remediate.candidate import Candidate, RefusedCandidate
lazy from odfa11y.remediate.execute import execute_decisions, require_remediable
lazy from odfa11y.remediate.result import PublicationState, RemediationResult, Violation

__all__ = [
    "Candidate",
    "PublicationState",
    "RefusedCandidate",
    "RemediationResult",
    "Violation",
    "execute_decisions",
    "require_remediable",
]
