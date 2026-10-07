# SPDX-License-Identifier: MPL-2.0
"""Bind the text family's language to its paragraph style."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.content import set_style_language, style_language

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument


def default_language(document: OdfDocument) -> str | None:
    """Read the family's default language.

    Returns
    -------
    str | None
        The language declared on its default style.

    """
    return style_language(document, "paragraph")


def set_default_language(document: OdfDocument, tag: str) -> bool:
    """Write the family's default language.

    Returns
    -------
    bool
        Whether the style changed.

    """
    return set_style_language(document, tag, "paragraph")
