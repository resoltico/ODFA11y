# SPDX-License-Identifier: MPL-2.0
"""Normalize only permitted address wrappers and reviewed header representations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.content import protected_xml, repeated
from odfa11y.odf import qn

from .links import URI_RE, split_trailing_punctuation

if TYPE_CHECKING:
    from lxml import etree


def unwrap_address(source: etree._Element, target: etree._Element) -> None:
    """Remove only a newly created exact address wrapper in a protected copy."""
    token = source.text or ""
    match = URI_RE.fullmatch(token)
    if not match or len(source):
        return
    address, punctuation = split_trailing_punctuation(token)
    expected = f"mailto:{address}" if match.group("email") else address
    if punctuation or dict(source.attrib) != {
        qn("xlink", "type"): "simple",
        qn("xlink", "href"): expected,
    }:
        return
    parent = target.getparent()
    if parent is None:
        return
    value = token + (target.tail or "")
    previous = target.getprevious()
    if previous is None:
        parent.text = (parent.text or "") + value
    else:
        previous.tail = (previous.tail or "") + value
    parent.remove(target)


def normalize_headers(table: etree._Element) -> None:
    """Ignore this table's header wrappers and coalesce proven identical repeated runs."""
    for node in list(
        table.iter(qn("table", "table-header-rows"), qn("table", "table-header-columns"))
    ):
        parent = node.getparent()
        owner = next(node.iterancestors(qn("table", "table")), None)
        if parent is None or owner is not table:
            continue
        position = parent.index(node)
        for offset, child in enumerate(list(node)):
            parent.insert(position + offset, child)
        parent.remove(node)
    for parent in table.iter():
        owner = (
            parent
            if parent.tag == qn("table", "table")
            else next(parent.iterancestors(qn("table", "table")), None)
        )
        if owner is not table:
            continue
        _coalesce_declarations(parent)


def _coalesce_declarations(parent: etree._Element) -> None:
    previous = None
    for child in list(parent):
        if child.tag not in {qn("table", "table-row"), qn("table", "table-column")}:
            previous = None
            continue
        repeat = qn(
            "table",
            "number-rows-repeated"
            if child.tag == qn("table", "table-row")
            else "number-columns-repeated",
        )
        count = str(repeated(child, repeat.rsplit("}", 1)[-1]))
        child.attrib.pop(repeat, None)
        if child.tail and not child.tail.strip():
            child.tail = None
        if previous is not None:
            old_count = previous.attrib.pop(repeat, "1")
            equal = protected_xml(previous) == protected_xml(child)
            previous.set(repeat, old_count)
            if equal:
                previous.set(repeat, str(int(old_count) + int(count)))
                parent.remove(child)
                continue
        child.set(repeat, count)
        previous = child
