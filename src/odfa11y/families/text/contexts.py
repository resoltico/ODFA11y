# SPDX-License-Identifier: MPL-2.0
"""Views of established current Writer flow and excluded authored contexts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.content import eligible_text_node, text_context_path
from odfa11y.odf import qn, select_elements
from odfa11y.report import Location

if TYPE_CHECKING:
    from lxml import etree


def text_nodes(
    tree: etree._ElementTree, *tags: str, main_only: bool = False
) -> list[etree._Element]:
    """Select established current-flow nodes, optionally limited to the main outline.

    Returns
    -------
    list[etree._Element]
        Nodes in document order, without entering excluded contexts.

    """
    wanted = set(tags)
    return [
        node
        for node in select_elements(tree, "//office:body//*")
        if node.tag in wanted and eligible_text_node(node, main_only=main_only)
    ]


def context_name(node: etree._Element) -> str:
    """Qualify a target by its enclosing note or text box.

    Returns
    -------
    str
        The logical context prefix; main body retains content.

    """
    return text_context_path(node)


def context_location(
    node: etree._Element, kind: str, index: int, name: str | None = None
) -> Location:
    """Address a target within its current-flow context.

    Returns
    -------
    Location
        A context-qualified named or ordinal location.

    """
    context = context_name(node)
    return Location.named(context, kind, name) if name else Location.indexed(context, kind, index)


def has_revisions(tree: etree._ElementTree) -> bool:
    """Whether declarations or markers make editing scope unestablished.

    Returns
    -------
    bool
        True even for an empty tracked-change declaration.

    """
    return any(
        node.tag
        in {
            qn("text", name) for name in ("tracked-changes", "change", "change-start", "change-end")
        }
        for node in tree.iter()
    )
