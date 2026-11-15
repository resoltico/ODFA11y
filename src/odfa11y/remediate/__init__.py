# SPDX-License-Identifier: MPL-2.0
"""Run explicit, content-preserving operations on an ODF document under one executor."""

from odfa11y.remediate.execute import remediate
from odfa11y.remediate.metadata import SetMetadata
from odfa11y.remediate.result import RemediationResult, Violation
from odfa11y.remediate.version import SetOdfVersion

__all__ = ["RemediationResult", "SetMetadata", "SetOdfVersion", "Violation", "remediate"]
