# SPDX-License-Identifier: MPL-2.0
"""Review table contents independently of permitted header and repeat representations."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.odf import qn, select_elements

from .graphic_style_identity import normalized_graphic_tree
from .tables import declarations, repeated
from .text import visible_words
from .xml import attribute_bindings, protected_xml

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument


def table_fingerprint(table: etree._Element, document: OdfDocument | None = None) -> str:
    """Fingerprint full table data without header-wrapper or description metadata.

    Returns
    -------
    str
        The reviewed table identity and all protected rows/cell attributes and words.

    """
    return _fingerprint(
        normalized_graphic_tree(document, table) if document is not None else table,
        include_styles=True,
    )


def table_content_fingerprint(table: etree._Element, document: OdfDocument | None = None) -> str:
    """Fingerprint logical data independently of generated style names.

    Returns
    -------
    str
        Protected words, values, formulas and grid structure.

    """
    return _fingerprint(
        normalized_graphic_tree(document, table) if document is not None else table,
        include_styles=False,
    )


def _attributes(node: etree._Element, repeat: str, *, include_styles: bool) -> dict[str, str]:
    excluded = {qn("table", repeat)}
    if not include_styles:
        excluded.add(qn("table", "style-name"))
    return {k: v for k, v in node.attrib.items() if k not in excluded}


def _fingerprint(table: etree._Element, *, include_styles: bool) -> str:
    columns = []
    for column in declarations(table, "columns"):
        count = repeated(column, "number-columns-repeated")
        attributes = _attributes(column, "number-columns-repeated", include_styles=include_styles)
        if columns and columns[-1][0] == attributes:
            columns[-1] = (attributes, columns[-1][1] + count)
        else:
            columns.append((attributes, count))
    facts = [table.get(qn("table", "name")), columns]
    runs: list[tuple[object, int]] = []
    for row in declarations(table, "rows"):
        cells = [
            _cell_facts(cell, include_styles=include_styles)
            for cell in select_elements(row, "./table:table-cell | ./table:covered-table-cell")
        ]
        attributes = _attributes(row, "number-rows-repeated", include_styles=include_styles)
        value = [
            attributes,
            attribute_bindings(row, omitted_attributes=(qn("table", "number-rows-repeated"),)),
            cells,
        ]
        count = repeated(row, "number-rows-repeated")
        if runs and runs[-1][0] == value:
            runs[-1] = (value, runs[-1][1] + count)
        else:
            runs.append((value, count))
    facts.extend(runs)
    return hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()[:16]


def _cell_facts(cell: etree._Element, *, include_styles: bool) -> list[object]:
    normalized = _nested_table_representation(cell)
    return [
        cell.tag,
        attribute_bindings(
            cell, omitted_attributes=() if include_styles else (qn("table", "style-name"),)
        ),
        _attributes(cell, "unused", include_styles=include_styles),
        visible_words(normalized),
        protected_xml(
            normalized,
            omitted_elements=(qn("svg", "title"), qn("svg", "desc")),
            omitted_root_attributes=() if include_styles else (qn("table", "style-name"),),
            omitted_element_attributes={
                qn(ns, "a"): (qn("office", "title"),) for ns in ("draw", "text")
            },
        ),
    ]


def _nested_table_representation(cell: etree._Element) -> etree._Element:
    clone = etree.Element(cell.tag, nsmap=cell.nsmap)
    clone.attrib.update(cell.attrib)
    clone.text, clone.tail = cell.text, cell.tail
    clone.extend(deepcopy(child) for child in cell)
    for table in reversed(list(clone.iter(qn("table", "table")))):
        _unwrap_headers(table)
        for parent in table.iter():
            owner = (
                parent
                if parent is table
                else next(parent.iterancestors(qn("table", "table")), None)
            )
            if owner is table:
                _coalesce(parent)
    return clone


def _unwrap_headers(table: etree._Element) -> None:
    for wrapper in list(
        table.iter(qn("table", "table-header-rows"), qn("table", "table-header-columns"))
    ):
        owner = next(wrapper.iterancestors(qn("table", "table")), None)
        parent = wrapper.getparent()
        if owner is not table or parent is None or wrapper.attrib:
            continue
        position = parent.index(wrapper)
        for offset, child in enumerate(list(wrapper)):
            parent.insert(position + offset, child)
        parent.remove(wrapper)


def _coalesce(parent: etree._Element) -> None:
    previous = None
    for child in list(parent):
        if child.tag not in {qn("table", "table-row"), qn("table", "table-column")}:
            previous = None
            continue
        attribute = (
            "number-rows-repeated"
            if child.tag == qn("table", "table-row")
            else "number-columns-repeated"
        )
        repeat = qn("table", attribute)
        child.set(repeat, str(repeated(child, attribute)))
        if child.tail and not child.tail.strip():
            child.tail = None
        if (
            previous is not None
            and previous.tag == child.tag
            and _declaration_xml(previous, repeat) == _declaration_xml(child, repeat)
        ):
            previous.set(repeat, str(repeated(previous, attribute) + repeated(child, attribute)))
            parent.remove(child)
        else:
            previous = child


def _declaration_xml(node: etree._Element, repeat: str) -> str:
    return protected_xml(
        node,
        omitted_root_attributes=(repeat,),
        omitted_elements=(qn("svg", "title"), qn("svg", "desc")),
        omitted_element_attributes={
            qn(ns, "a"): (qn("office", "title"),) for ns in ("draw", "text")
        },
    )
