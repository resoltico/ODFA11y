# SPDX-License-Identifier: MPL-2.0
"""ODF XML namespace prefixes and qualified-name construction."""

from __future__ import annotations

NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "svg": "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "dc": "http://purl.org/dc/elements/1.1/",
    "meta": "urn:oasis:names:tc:opendocument:xmlns:meta:1.0",
    "manifest": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
}


def qn(prefix: str, local: str) -> str:
    """Expand a namespace prefix and local name into a qualified XML name.

    Returns
    -------
    str
        The expanded XML namespace name.

    """
    return f"{{{NS[prefix]}}}{local}"
