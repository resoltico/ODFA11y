# SPDX-License-Identifier: MPL-2.0
"""Read and write language declarations on shared ODF style vocabulary."""

from __future__ import annotations

import re
from itertools import starmap
from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.odf import NS, Part, qn, select_elements

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument


# RFC 5646 grandfathered tags have an explicitly enumerated syntax.
_GRANDFATHERED: dict[str, str] = {
    tag.lower(): tag
    for tag in (
        "en-GB-oed",
        "i-ami",
        "i-bnn",
        "i-default",
        "i-enochian",
        "i-hak",
        "i-klingon",
        "i-lux",
        "i-mingo",
        "i-navajo",
        "i-pwn",
        "i-tao",
        "i-tay",
        "i-tsu",
        "sgn-BE-FR",
        "sgn-BE-NL",
        "sgn-CH-DE",
        "art-lojban",
        "cel-gaulish",
        "no-bok",
        "no-nyn",
        "zh-guoyu",
        "zh-hakka",
        "zh-min",
        "zh-min-nan",
        "zh-xiang",
    )
}
_TAG = re.compile(
    r"(?P<language>[A-Za-z]{2,3}(?:-[A-Za-z]{3}){0,3}|[A-Za-z]{4}|[A-Za-z]{5,8})"
    r"(?P<script>-[A-Za-z]{4})?(?P<region>-(?:[A-Za-z]{2}|[0-9]{3}))?"
    r"(?P<variants>(?:-(?:[A-Za-z0-9]{5,8}|[0-9][A-Za-z0-9]{3}))*)"
    r"(?P<extensions>(?:-[0-9A-WY-Za-wy-z](?:-[A-Za-z0-9]{2,8})+)*)"
    r"(?P<private>-x(?:-[A-Za-z0-9]{1,8})+)?"
)
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


def normalize_language(tag: str) -> str:
    """Validate RFC 5646 syntax and normalize separators and subtag casing.

    No registry or preferred-alias lookup is performed.

    Returns
    -------
    str
        The normalized, lossless language tag.

    Raises
    ------
    ValueError
        The tag is malformed or repeats a variant or extension singleton.

    """
    value = tag.strip().replace("_", "-")
    if value.lower() in _GRANDFATHERED:
        return _GRANDFATHERED[value.lower()]
    if re.fullmatch(r"x(?:-[A-Za-z0-9]{1,8})+", value, re.IGNORECASE):
        return value.lower()
    match = _TAG.fullmatch(value)
    if match is None:
        msg = f"Invalid language tag: {tag!r}"
        raise ValueError(msg)
    variants = match["variants"].lower().split("-")[1:]
    singletons = re.findall(r"(?:^|-)([0-9a-wy-z])(?=-)", match["extensions"].lower())
    if len(set(variants)) != len(variants) or len(set(singletons)) != len(singletons):
        msg = f"Invalid language tag with repeated variant or extension: {tag!r}"
        raise ValueError(msg)
    return (
        match["language"].lower()
        + (match["script"].title() if match["script"] else "")
        + (match["region"].upper() if match["region"] else "")
        + match["variants"].lower()
        + match["extensions"].lower()
        + (match["private"].lower() if match["private"] else "")
    )


def _representation(tag: str) -> tuple[str | None, ...]:
    match = _TAG.fullmatch(tag)
    if (
        match is None
        or "-" in match["language"]
        or any(match[key] for key in ("variants", "extensions", "private"))
        or tag.lower() in _GRANDFATHERED
    ):
        return None, None, None, tag
    return (
        match["language"],
        (match["script"] or "")[1:] or None,
        (match["region"] or "")[1:] or None,
        None,
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
    values = _representation(tag)
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
