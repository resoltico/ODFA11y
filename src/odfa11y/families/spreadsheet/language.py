# SPDX-License-Identifier: MPL-2.0
"""A spreadsheet's default language, which lives on its default cell style."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.odf import NS, Part, qn, select_elements

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument

DEFAULT_STYLE = "//office:styles/style:default-style[@style:family='table-cell']"


def default_language(document: OdfDocument) -> str | None:
    """Read the language declared on the default cell style.

    Returns
    -------
    str | None
        ``language`` or ``language-COUNTRY``, or None when the style declares none.

    """
    if not document.has(Part.STYLES):
        return None
    props = _text_properties(document.tree(Part.STYLES))
    if props is None:
        return None
    language = props.get(qn("fo", "language"))
    country = props.get(qn("fo", "country"))
    if language and country and country.lower() != "none":
        return f"{language}-{country}"
    return language


def set_default_language(document: OdfDocument, tag: str) -> bool:
    """Declare a language tag on the default cell style when it differs.

    Returns
    -------
    bool
        True when the style was edited; False when it already matched or the document has
        no styles part to carry it.

    """
    if not document.has(Part.STYLES):
        return False
    language, country = split_language(tag)
    props = _text_properties(document.tree(Part.STYLES))
    current = (
        (props.get(qn("fo", "language")), props.get(qn("fo", "country")))
        if props is not None
        else (None, None)
    )
    if current == (language, country):
        return False
    props = _ensure_text_properties(document.edit(Part.STYLES))
    props.set(qn("fo", "language"), language)
    if country:
        props.set(qn("fo", "country"), country)
    else:
        props.attrib.pop(qn("fo", "country"), None)
    return True


def split_language(tag: str) -> tuple[str, str | None]:
    """Split a language tag into a lower-case language and an upper-case country.

    Returns
    -------
    tuple[str, str | None]
        The language subtag and the first two-letter region subtag, if any.

    """
    parts = tag.replace("_", "-").split("-")
    country = next((part.upper() for part in parts[1:] if re.fullmatch(r"[A-Za-z]{2}", part)), None)
    return parts[0].lower(), country


def _text_properties(styles: etree._ElementTree) -> etree._Element | None:
    nodes = select_elements(styles, f"{DEFAULT_STYLE}/style:text-properties")
    return nodes[0] if nodes else None


def _ensure_text_properties(styles: etree._ElementTree) -> etree._Element:
    existing = _text_properties(styles)
    if existing is not None:
        return existing
    container = styles.find("office:styles", NS)
    if container is None:
        container = _insert_styles_container(styles.getroot())
    defaults = select_elements(container, "./style:default-style[@style:family='table-cell']")
    if defaults:
        default = defaults[0]
    else:
        default = etree.Element(qn("style", "default-style"))
        default.set(qn("style", "family"), "table-cell")
        container.insert(0, default)
    return etree.SubElement(default, qn("style", "text-properties"))


def _insert_styles_container(root: etree._Element) -> etree._Element:
    """Create ``office:styles`` where the schema allows it: before automatic/master styles and body.

    Returns
    -------
    etree._Element
        The new, empty ``office:styles`` element.

    """
    container = etree.Element(qn("office", "styles"))
    later = {qn("office", name) for name in ("automatic-styles", "master-styles", "body")}
    position = next((index for index, child in enumerate(root) if child.tag in later), len(root))
    root.insert(position, container)
    return container
