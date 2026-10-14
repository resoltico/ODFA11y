# SPDX-License-Identifier: MPL-2.0
"""Normalize only proven paragraph-spacing references in supplementary grid snapshots."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from odfa11y.content import eligible_text_node
from odfa11y.errors import RemediationError, XmlParseError
from odfa11y.odf import qn

from .derived_styles import NO_STYLE, derived_style_name, is_generated_from
from .styles import catalog_of

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument


def normalized_spacing_tree(document: OdfDocument, root: etree._Element) -> etree._Element:
    """Restore original references only for established generated paragraph styles.

    Returns
    -------
    etree._Element
        A copy retaining every unproven or excluded-context style reference.

    """
    clone = deepcopy(root)
    nodes = [
        target
        for source, target in zip(root.iter(), clone.iter(), strict=True)
        if source.tag in {qn("text", "p"), qn("text", "h")}
        and eligible_text_node(source, main_only=True)
        and not any(
            qn("text", name) in source.attrib for name in ("class-names", "cond-style-name")
        )
    ]
    used = {node.get(qn("text", "style-name")) for node in nodes}
    if not any(name and name.startswith("A11ySpacing_") for name in used):
        return clone
    try:
        proven = _proven_references(document, used)
    except RemediationError, XmlParseError:
        return clone  # Unknown definitions cannot authorize normalization.
    for node in nodes:
        name = node.get(qn("text", "style-name"))
        if name not in proven:
            continue
        if proven[name] == NO_STYLE:
            node.attrib.pop(qn("text", "style-name"), None)
        else:
            node.set(qn("text", "style-name"), proven[name])
    return clone


def _proven_references(document: OdfDocument, used: set[str | None]) -> dict[str, str]:
    catalog = catalog_of(document)
    bases = {
        NO_STYLE,
        *(style.get(qn("style", "name"), "") for style in catalog.styles("paragraph")),
    }
    proven = {}
    for base in bases:
        name = derived_style_name(base)
        if name not in used:
            continue
        style = catalog.style("paragraph", name)
        if style is not None and is_generated_from(
            catalog, style, None if base == NO_STYLE else base, name
        ):
            proven[name] = base
    return proven
