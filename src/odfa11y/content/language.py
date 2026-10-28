# SPDX-License-Identifier: MPL-2.0
"""Read and write language declarations on shared ODF style vocabulary."""

from __future__ import annotations

from itertools import starmap
from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.language_tags import language_parts, normalize_language
from odfa11y.odf import NS, Part, qn, select_elements

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument

CHANNEL_ATTRIBUTES = tuple(
    tuple(starmap(qn, attributes))
    for attributes in (
        (("fo", "language"), ("fo", "script"), ("fo", "country"), ("style", "rfc-language-tag")),
        tuple(
            ("style", name + "-asian")
            for name in ("language", "script", "country", "rfc-language-tag")
        ),
        tuple(
            ("style", name + "-complex")
            for name in ("language", "script", "country", "rfc-language-tag")
        ),
    )
)


def style_language(document: OdfDocument, family: str, channel: int = 0) -> str | None:
    """Read the full tag or component declaration of one default script channel.

    Channels are western (0), Asian (1), and complex (2).

    Returns
    -------
    str | None
        The complete declaration, or None for an unspecified default.

    """
    if not document.has(Part.STYLES):
        return None
    props = _text_properties(document.tree(Part.STYLES), family)
    if props is None:
        return None
    language, script, country, full = (props.get(key) for key in CHANNEL_ATTRIBUTES[channel])
    if full and full.lower() != "none":
        return normalize_language(full)
    if not language or language.lower() == "none":
        return None
    components = [
        language,
        *(part for part in (script, country) if part and part.lower() != "none"),
    ]
    return normalize_language("-".join(components))


def set_style_language(document: OdfDocument, tag: str, family: str) -> bool:
    """Replace all three default script channels without editing authored overrides.

    Returns
    -------
    bool
        Whether a style was edited; absent styles parts remain optional.

    """
    tag = normalize_language(tag)
    if not document.has(Part.STYLES):
        return False
    values = language_parts(tag)
    props = _text_properties(document.tree(Part.STYLES), family)
    desired = {
        key: value
        for channel in CHANNEL_ATTRIBUTES
        for key, value in zip(channel, values, strict=True)
    }
    if props is not None and all(props.get(key) == value for key, value in desired.items()):
        return False
    props = _ensure_text_properties(document.tree(Part.STYLES), family)
    for key, value in desired.items():
        if value is None:
            props.attrib.pop(key, None)
        else:
            props.set(key, value)
    return True


def _text_properties(styles: etree._ElementTree, family: str) -> etree._Element | None:
    containers = select_elements(styles, "./office:styles")
    if len(containers) > 1:
        msg = "Ambiguous office:styles language target."
        raise ValueError(msg)
    defaults = select_elements(
        styles, f"./office:styles/style:default-style[@style:family='{family}']"
    )
    if len(defaults) > 1:
        msg = f"Ambiguous default {family} style language target."
        raise ValueError(msg)
    nodes = select_elements(defaults[0], "./style:text-properties") if defaults else []
    if len(nodes) > 1:
        msg = f"Ambiguous default {family} text-properties language target."
        raise ValueError(msg)
    return nodes[0] if nodes else None


def _ensure_text_properties(styles: etree._ElementTree, family: str) -> etree._Element:
    existing = _text_properties(styles, family)
    if existing is not None:
        return existing
    container = styles.find("office:styles", NS)
    if container is None:
        container = _insert_styles_container(styles.getroot())
    defaults = select_elements(container, f"./style:default-style[@style:family='{family}']")
    if defaults:
        default = defaults[0]
    else:
        default = etree.Element(qn("style", "default-style"))
        default.set(qn("style", "family"), family)
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
