# SPDX-License-Identifier: MPL-2.0
"""Resolve paragraph and nested inline language through scoped ODF styles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.content import CHANNEL_ATTRIBUTES, reading_context_path
from odfa11y.errors import RemediationError
from odfa11y.families.text.contexts import text_nodes
from odfa11y.families.text.style_properties import paragraph_style_name
from odfa11y.families.text.styles import catalog_of
from odfa11y.language_tags import normalize_language
from odfa11y.odf import Part, qn
from odfa11y.report import Location

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument

CHANNELS = ("western", "asian", "complex")
BLOCKS = {qn("text", "p"), qn("text", "h")}
INLINE = {qn("text", "span"), qn("text", "a")}


def language_nodes(document: OdfDocument) -> list[etree._Element]:
    """Select current paragraph, heading and inline language targets.

    Returns
    -------
    list[etree._Element]
        Stable source-order targets, including note and text-box reading contexts.

    """
    return text_nodes(document.tree(Part.CONTENT), *BLOCKS, *INLINE)


def language_location(node: etree._Element, index: int) -> Location:
    """Locate one language target by its source ordinal within its reading context.

    Returns
    -------
    Location
        Canonical source-bound target.

    """
    return Location.indexed(reading_context_path(node), "language", index)


def effective_languages(document: OdfDocument, node: etree._Element) -> tuple[str | None, ...]:
    """Overlay paragraph and nested inline styles, retaining distinct script channels.

    Returns
    -------
    tuple[str | None, ...]
        Western, Asian and complex language tags; unspecified channels stay None.

    """
    return languages_from_properties(effective_text_properties(document, node))


def effective_text_properties(document: OdfDocument, node: etree._Element) -> dict[str, str]:
    """Resolve the text attributes used by language and override preflight.

    Returns
    -------
    dict[str, str]
        Inherited properties in effective precedence order.

    Raises
    ------
    RemediationError
        The paragraph or style scope is unresolved.

    """
    catalog = catalog_of(document)
    ancestors = [node, *node.iterancestors()]
    block = next((ancestor for ancestor in ancestors if ancestor.tag in BLOCKS), None)
    if block is None:
        msg = "Inline language has no established paragraph context."
        raise RemediationError(msg)
    props = catalog.effective_text_properties(paragraph_style_name(block))
    inline = ancestors[: ancestors.index(block)]
    for styled in reversed(inline):
        if styled.tag in INLINE:
            props.update(
                catalog.effective_properties(
                    "text", paragraph_style_name(styled), "text-properties"
                )
            )
    return props


def languages_from_properties(props: dict[str, str]) -> tuple[str | None, ...]:
    """Read all script channels from already resolved style properties.

    Returns
    -------
    tuple[str | None, ...]
        Western, Asian and complex tags.

    """
    return tuple(_channel(props, attributes) for attributes in CHANNEL_ATTRIBUTES)


def _channel(props: dict[str, str], attributes: tuple[str, ...]) -> str | None:
    language, script, country, full = (props.get(key) for key in attributes)
    try:
        if full and full.lower() != "none":
            return normalize_language(full)
        if not language or language.lower() == "none":
            return None
        return normalize_language(
            "-".join(
                component
                for component in (language, script, country)
                if component and component.lower() != "none"
            )
        )
    except ValueError as error:
        msg = "Effective style language is not a valid language tag."
        raise RemediationError(msg) from error


def language_targets(document: OdfDocument) -> dict[str, etree._Element]:
    """Index language targets with independent ordinals for each reading context.

    Returns
    -------
    dict[str, etree._Element]
        Canonical logical targets in source order.

    """
    return document.derived("text.language_targets", lambda: _language_targets(document))


def _language_targets(document: OdfDocument) -> dict[str, etree._Element]:
    counts: dict[str, int] = {}
    targets = {}
    for node in language_nodes(document):
        context = reading_context_path(node)
        counts[context] = counts.get(context, 0) + 1
        targets[language_location(node, counts[context]).path] = node
    return targets
