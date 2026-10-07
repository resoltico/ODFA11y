# SPDX-License-Identifier: MPL-2.0
"""The text family: audit rules, operations and plan tables for text documents."""

from .adapter import ADAPTER
from .graphics import SetGraphicDescriptions
from .headings import HeadingLevel, SetHeadingLevels
from .link_probe import write_link_probe
from .linkify import LinkifyAddresses, linkify_plain_addresses
from .links import URI_RE, split_trailing_punctuation
from .remove_spacers import RemoveEmptySpacers
from .spacing import NormalizeSpacing, derived_style_name
from .tables import MarkTableHeaders, TableHeaders
from .text import text_is_preserved

__all__ = [
    "ADAPTER",
    "URI_RE",
    "HeadingLevel",
    "LinkifyAddresses",
    "MarkTableHeaders",
    "NormalizeSpacing",
    "RemoveEmptySpacers",
    "SetGraphicDescriptions",
    "SetHeadingLevels",
    "TableHeaders",
    "derived_style_name",
    "linkify_plain_addresses",
    "split_trailing_punctuation",
    "text_is_preserved",
    "write_link_probe",
]
