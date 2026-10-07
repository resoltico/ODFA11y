# SPDX-License-Identifier: MPL-2.0
"""Native formula identity, language and mathematical-expression preservation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.content import protected_xml
from odfa11y.odf import Part, qn

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument

XML_LANGUAGE = "{http://www.w3.org/XML/1998/namespace}lang"
EDITABLE = ("alttext", XML_LANGUAGE)


def expression(document: OdfDocument) -> etree._Element | None:
    """Read the native MathML root without inventing an office-body wrapper.

    Returns
    -------
    etree._Element | None
        The formula, or None for a representation outside this adapter's contract.

    """
    root = document.tree(Part.CONTENT).getroot()
    return root if root.tag == qn("math", "math") else None


def fingerprint(root: etree._Element) -> str:
    """Bind an alternative to the expression, annotations and presentation attributes.

    Returns
    -------
    str
        A reviewed digest excluding only spoken alternative and root language.

    """
    return protected_xml(root, omitted_root_attributes=EDITABLE)[:16]


def snapshot(document: OdfDocument) -> tuple[str, ...]:
    """Protect mathematical structure, annotations, references and every other attribute.

    Returns
    -------
    tuple[str, ...]
        The complete protected expression digest.

    """
    return (protected_xml(document.tree(Part.CONTENT).getroot(), omitted_root_attributes=EDITABLE),)


def language(document: OdfDocument) -> str | None:
    """Read the formula's explicit root language.

    Returns
    -------
    str | None
        The declared language when the representation is supported.

    """
    root = expression(document)
    return root.get(XML_LANGUAGE) if root is not None else None


def set_language(document: OdfDocument, tag: str) -> bool:
    """Set the formula language without changing the mathematical expression.

    Returns
    -------
    bool
        Whether the supported root's language changed.

    """
    root = expression(document)
    if root is None or root.get(XML_LANGUAGE) == tag:
        return False
    document.edit(Part.CONTENT)
    root.set(XML_LANGUAGE, tag)
    return True
