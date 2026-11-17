# SPDX-License-Identifier: AGPL-3.0-only
"""Bind the text family's language to its paragraph style."""

from odfa11y.concepts import set_style_language, style_language
from odfa11y.odf.allowance import XmlChange
lazy from odfa11y.odf import OdfDocument


def default_language(document: OdfDocument) -> str | None:
    """Read the family's default language.

    Returns
    -------
    str | None
        The language declared on its default style.

    """
    return style_language(document, "paragraph")


def set_default_language(document: OdfDocument, tag: str) -> XmlChange:
    """Write the family's default language.

    Returns
    -------
    bool
        Whether the style changed.

    """
    return set_style_language(document, tag, "paragraph")
