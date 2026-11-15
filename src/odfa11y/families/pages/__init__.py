# SPDX-License-Identifier: MPL-2.0
"""Shared page semantics with two native-family registrations."""

from odfa11y.families.pages.operations import (
    SetGraphicAlternatives,
    SetLinkDescriptions,
    SetPageSemantics,
)
from odfa11y.families.pages.spec import DRAWING_ADAPTER, PRESENTATION_ADAPTER

__all__ = [
    "DRAWING_ADAPTER",
    "PRESENTATION_ADAPTER",
    "SetGraphicAlternatives",
    "SetLinkDescriptions",
    "SetPageSemantics",
]
