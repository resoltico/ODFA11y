# SPDX-License-Identifier: MPL-2.0
"""The text family: audit rules, operations and plan tables for text documents."""

from .adapter import ADAPTER
from .graphics import AltText, SetAltText
from .linkify import LinkifyAddresses, linkify_plain_addresses
from .links import URI_RE, split_trailing_punctuation
from .remove_spacers import RemoveEmptySpacers
from .spacing import NormalizeSpacing, derived_style_name
from .tables import HeaderRows, MarkHeaderRows
from .text import text_is_preserved

__all__ = [
    "ADAPTER",
    "URI_RE",
    "AltText",
    "HeaderRows",
    "LinkifyAddresses",
    "MarkHeaderRows",
    "NormalizeSpacing",
    "RemoveEmptySpacers",
    "SetAltText",
    "derived_style_name",
    "linkify_plain_addresses",
    "split_trailing_punctuation",
    "text_is_preserved",
]
