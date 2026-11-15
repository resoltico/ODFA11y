# SPDX-License-Identifier: MPL-2.0
"""Run explicit, content-preserving operations on an ODF document under one executor."""

lazy from odfa11y.remediate.execute import remediate
lazy from odfa11y.remediate.metadata import SetMetadata
lazy from odfa11y.remediate.result import RemediationResult, Violation
lazy from odfa11y.remediate.version import SetOdfVersion

__all__ = ["RemediationResult", "SetMetadata", "SetOdfVersion", "Violation", "remediate"]
