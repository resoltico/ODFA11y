# SPDX-License-Identifier: MPL-2.0
"""The text family: audit rules, operations and plan tables for text documents."""

from odfa11y.families.text.links.edit import linkify_plain_addresses
from odfa11y.families.text.links.urls import URI_RE, split_trailing_punctuation
from odfa11y.families.text.spec import SPEC
from odfa11y.odf.styles import derived_style_name

__all__ = [
    "SPEC",
    "URI_RE",
    "derived_style_name",
    "linkify_plain_addresses",
    "split_trailing_punctuation",
]
