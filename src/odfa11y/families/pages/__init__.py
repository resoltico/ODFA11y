# SPDX-License-Identifier: MPL-2.0
"""Shared page semantics with two native-family registrations."""

from .adapter import DRAWING_ADAPTER, PRESENTATION_ADAPTER
from .operations import SetGraphicAlternatives, SetLinkDescriptions, SetPageSemantics

__all__ = [
    "DRAWING_ADAPTER",
    "PRESENTATION_ADAPTER",
    "SetGraphicAlternatives",
    "SetLinkDescriptions",
    "SetPageSemantics",
]
