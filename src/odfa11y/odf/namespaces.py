# SPDX-License-Identifier: MPL-2.0
"""ODF XML namespace prefixes and qualified-name construction."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lxml import etree

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
    "chart": "urn:oasis:names:tc:opendocument:xmlns:chart:1.0",
    "db": "urn:oasis:names:tc:opendocument:xmlns:database:1.0",
    "form": "urn:oasis:names:tc:opendocument:xmlns:form:1.0",
    "presentation": "urn:oasis:names:tc:opendocument:xmlns:presentation:1.0",
    "script": "urn:oasis:names:tc:opendocument:xmlns:script:1.0",
    "dr3d": "urn:oasis:names:tc:opendocument:xmlns:dr3d:1.0",
    "math": "http://www.w3.org/1998/Math/MathML",
    "manifest": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
}


def is_office_element(element: etree._Element) -> bool:
    """Whether an element is in the ODF ``office`` namespace (a document root, not MathML).

    Returns
    -------
    bool
        True for elements such as ``office:document-content``; False for comments and others.

    """
    return isinstance(element.tag, str) and element.tag.startswith(f"{{{NS['office']}}}")


def qn(prefix: str, local: str) -> str:
    """Expand a namespace prefix and local name into a qualified XML name.

    Returns
    -------
    str
        The expanded XML namespace name.

    """
    return f"{{{NS[prefix]}}}{local}"
