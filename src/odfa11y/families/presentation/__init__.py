# SPDX-License-Identifier: MPL-2.0
"""Family-bound semantic audit, configuration and operations."""

from .adapter import ADAPTER
from .operations import SetGraphicAlternatives, SetLinkDescriptions, SetPageSemantics

__all__ = ["ADAPTER", "SetGraphicAlternatives", "SetLinkDescriptions", "SetPageSemantics"]
