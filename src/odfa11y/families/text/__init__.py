# SPDX-License-Identifier: MPL-2.0
"""The text family: audit rules, operations and plan tables for text documents."""

from odfa11y.families.text.flow import text_is_preserved
from odfa11y.families.text.links.edit import linkify_plain_addresses
from odfa11y.families.text.links.urls import URI_RE, split_trailing_punctuation
from odfa11y.families.text.spec import ADAPTER
from odfa11y.families.text.styles.catalogue import derived_style_name

__all__ = [
    "ADAPTER",
    "URI_RE",
    "derived_style_name",
    "linkify_plain_addresses",
    "split_trailing_punctuation",
    "text_is_preserved",
]
