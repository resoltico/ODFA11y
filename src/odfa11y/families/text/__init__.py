# SPDX-License-Identifier: MPL-2.0
"""The text family: audit rules, operations and plan tables for text documents."""

from odfa11y.families.text.flow import text_is_preserved
from odfa11y.families.text.graphics import SetGraphicAlternatives, SetLinkDescriptions
from odfa11y.families.text.headings.edit import HeadingLevel, SetHeadingLevels
from odfa11y.families.text.language.operations import SetTargetLanguages, TargetLanguage
from odfa11y.families.text.links.edit import LinkifyAddresses, linkify_plain_addresses
from odfa11y.families.text.links.urls import URI_RE, split_trailing_punctuation
from odfa11y.families.text.spacing.edit import NormalizeSpacing
from odfa11y.families.text.spacing.remove import RemoveEmptySpacers
from odfa11y.families.text.spec import ADAPTER
from odfa11y.families.text.styles.catalogue import derived_style_name
from odfa11y.families.text.tables import MarkTableHeaders, TableHeaders

__all__ = [
    "ADAPTER",
    "URI_RE",
    "HeadingLevel",
    "LinkifyAddresses",
    "MarkTableHeaders",
    "NormalizeSpacing",
    "RemoveEmptySpacers",
    "SetGraphicAlternatives",
    "SetHeadingLevels",
    "SetLinkDescriptions",
    "SetTargetLanguages",
    "TableHeaders",
    "TargetLanguage",
    "derived_style_name",
    "linkify_plain_addresses",
    "split_trailing_punctuation",
    "text_is_preserved",
]
