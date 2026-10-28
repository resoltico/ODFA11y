# SPDX-License-Identifier: MPL-2.0
"""Author explicit graphic style contexts for positive and adversarial source fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.content.graphic_styles import ROLE
from odfa11y.odf import NS, Part, qn

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument


def _style(
    document: OdfDocument,
    name: str,
    *,
    role: str | None = None,
    parent: str | None = None,
    automatic: bool = False,
) -> etree._Element:
    part = Part.CONTENT if automatic else Part.STYLES
    root = document.tree(part).getroot()
    styles = root.find("office:automatic-styles" if automatic else "office:styles", NS)
    if styles is None:
        styles = etree.Element(qn("office", "automatic-styles" if automatic else "styles"))
        following = next(
            (
                child
                for child in root
                if child.tag
                in {
                    qn("office", "automatic-styles"),
                    qn("office", "master-styles"),
                    qn("office", "body"),
                }
            ),
            None,
        )
        root.insert(root.index(following) if following is not None else len(root), styles)
    style = etree.SubElement(
        styles, qn("style", "style"), {qn("style", "name"): name, qn("style", "family"): "graphic"}
    )
    if parent:
        style.set(qn("style", "parent-style-name"), parent)
    props = etree.SubElement(
        style, qn("style", "graphic-properties"), {qn("draw", "fill-color"): "#112233"}
    )
    if role is not None:
        props.set(ROLE, role)
    return style
