# SPDX-License-Identifier: MPL-2.0
"""Read and edit ODF packages, XML content, styles and text."""

from .links import URI_RE, split_trailing_punctuation
from .namespaces import NS, qn
from .package import ODT_MIMETYPE, REQUIRED_XML, OdtPackage
from .styles import StyleCatalog
from .text import element_text, is_empty_paragraph, text_is_preserved, visible_text_snapshot
from .xpath import select_elements

__all__ = [
    "NS",
    "ODT_MIMETYPE",
    "REQUIRED_XML",
    "URI_RE",
    "OdtPackage",
    "StyleCatalog",
    "element_text",
    "is_empty_paragraph",
    "qn",
    "select_elements",
    "split_trailing_punctuation",
    "text_is_preserved",
    "visible_text_snapshot",
]
