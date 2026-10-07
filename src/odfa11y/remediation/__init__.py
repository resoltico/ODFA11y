# SPDX-License-Identifier: MPL-2.0
"""Run explicit, content-preserving operations on an ODF document under one executor."""

from .apply import remediate
from .metadata import SetMetadata
from .result import RemediationResult
from .version import SetOdfVersion

__all__ = ["RemediationResult", "SetMetadata", "SetOdfVersion", "remediate"]
