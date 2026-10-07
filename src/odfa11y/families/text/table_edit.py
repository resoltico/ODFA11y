# SPDX-License-Identifier: MPL-2.0
"""Wrap explicit leading header declarations without losing repeated data or groups."""

from __future__ import annotations

from copy import deepcopy

from lxml import etree

from odfa11y.content import AXES, declarations, repeated
from odfa11y.odf import qn


def mark_axis(table: etree._Element, axis: str, count: int) -> None:
    """Rebuild header wrappers for one already validated leading boundary."""
    _unwrap(table, axis)
    remaining = count
    for node in declarations(table, axis):
        if remaining == 0:
            break
        copies = repeated(node, AXES[axis][2])
        parent = node.getparent()
        if parent is None:
            continue
        if copies > remaining:
            tail = deepcopy(node)
            tail.set(qn("table", AXES[axis][2]), str(copies - remaining))
            parent.insert(parent.index(node) + 1, tail)
            node.set(qn("table", AXES[axis][2]), str(remaining))
            copies = remaining
        previous = node.getprevious()
        header_tag = qn("table", AXES[axis][1])
        if previous is not None and previous.tag == header_tag:
            wrapper = previous
        else:
            wrapper = etree.Element(header_tag)
            parent.insert(parent.index(node), wrapper)
        wrapper.append(node)
        remaining -= copies
    # The caller marks the document edited once the reviewed transformation is complete.


def _unwrap(table: etree._Element, axis: str) -> None:
    header_tag = qn("table", AXES[axis][1])
    for wrapper in list(table.iter(header_tag)):
        owner = next(wrapper.iterancestors(qn("table", "table")), None)
        parent = wrapper.getparent()
        if owner is not table or parent is None:
            continue
        position = parent.index(wrapper)
        for offset, node in enumerate(list(wrapper)):
            parent.insert(position + offset, node)
        parent.remove(wrapper)
