# SPDX-License-Identifier: MPL-2.0
"""Set document metadata text and the default paragraph language."""

from __future__ import annotations

import re

from lxml import etree

from odfa11y.odf import NS, qn, select_elements


def set_metadata_text(tree: etree._ElementTree, tag: str, value: str) -> bool:
    """Set a metadata element's text, reporting whether anything changed.

    Returns
    -------
    bool
        True when the tree was modified.

    """
    meta = tree.find("office:meta", NS)
    if meta is None:
        meta = etree.SubElement(tree.getroot(), qn("office", "meta"))
    node = meta.find(tag)
    if node is None:
        node = etree.SubElement(meta, tag)
    if (node.text or "") == value:
        return False
    node.text = value
    return True


def set_default_style_language(tree: etree._ElementTree, language_tag: str) -> bool:
    """Set the default style's language and country, reporting whether anything changed.

    Returns
    -------
    bool
        True when the tree was modified.

    """
    language, country = _split_language(language_tag)
    styles = tree.find("office:styles", NS)
    if styles is None:
        styles = etree.SubElement(tree.getroot(), qn("office", "styles"))
    defaults = select_elements(styles, "./style:default-style[@style:family='paragraph']")
    if defaults:
        default = defaults[0]
    else:
        default = etree.Element(qn("style", "default-style"))
        default.set(qn("style", "family"), "paragraph")
        styles.insert(0, default)
    props = default.find("style:text-properties", NS)
    if props is None:
        props = etree.SubElement(default, qn("style", "text-properties"))
    before = (props.get(qn("fo", "language")), props.get(qn("fo", "country")))
    props.set(qn("fo", "language"), language)
    if country:
        props.set(qn("fo", "country"), country)
    else:
        props.attrib.pop(qn("fo", "country"), None)
    after = (props.get(qn("fo", "language")), props.get(qn("fo", "country")))
    return before != after


def _split_language(tag: str) -> tuple[str, str | None]:
    parts = tag.replace("_", "-").split("-")
    if not parts[0] or not re.fullmatch(r"[A-Za-z]{2,8}", parts[0]):
        msg = f"Invalid language tag: {tag!r}"
        raise ValueError(msg)
    language = parts[0].lower()
    country = None
    for part in parts[1:]:
        if re.fullmatch(r"[A-Za-z]{2}", part):
            country = part.upper()
            break
    return language, country
