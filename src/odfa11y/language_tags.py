# SPDX-License-Identifier: MPL-2.0
"""Validate and represent lossless RFC 5646 language-tag values without XML dependencies."""

from __future__ import annotations

import re

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


def language_parts(tag: str) -> tuple[str | None, ...]:
    """Separate lossless basic components, retaining a full tag for complex syntax.

    Returns
    -------
    tuple[str | None, ...]
        Language, script, region and optional full-tag representation.

    """
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
