# SPDX-License-Identifier: MPL-2.0
"""Review table contents independently of permitted header and repeat representations."""

import json
from copy import deepcopy

from lxml import etree

from odfa11y.concepts.graphic_styles import normalized_graphic_tree
from odfa11y.concepts.tables import declarations, repeated
from odfa11y.concepts.text import visible_words
from odfa11y.concepts.xml import attribute_bindings, protected_xml
from odfa11y.odf import names as xml_names
from odfa11y.odf import qn, select_elements
from odfa11y.targets import Fingerprint
lazy from odfa11y.odf import OdfDocument


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
        excluded.add(xml_names.TABLE_STYLE_NAME)
    return {k: v for k, v in node.attrib.items() if k not in excluded}


def _fingerprint(table: etree._Element, *, include_styles: bool) -> Fingerprint:
    columns = []
    for column in declarations(table, "columns"):
        count = repeated(column, "number-columns-repeated")
        attributes = _attributes(column, "number-columns-repeated", include_styles=include_styles)
        if columns and columns[-1][0] == attributes:
            columns[-1] = (attributes, columns[-1][1] + count)
        else:
            columns.append((attributes, count))
    facts = [table.get(xml_names.TABLE_NAME), columns]
    runs: list[tuple[object, int]] = []
    for row in declarations(table, "rows"):
        cells = [
            _cell_facts(cell, include_styles=include_styles)
            for cell in select_elements(row, "./table:table-cell | ./table:covered-table-cell")
        ]
        attributes = _attributes(row, "number-rows-repeated", include_styles=include_styles)
        value = [
            attributes,
            attribute_bindings(row, omitted_attributes=(xml_names.TABLE_NUMBER_ROWS_REPEATED,)),
            cells,
        ]
        count = repeated(row, "number-rows-repeated")
        if runs and runs[-1][0] == value:
            runs[-1] = (value, runs[-1][1] + count)
        else:
            runs.append((value, count))
    facts.extend(runs)
    return Fingerprint.of(json.dumps(facts, sort_keys=True).encode())


def _cell_facts(cell: etree._Element, *, include_styles: bool) -> list[object]:
    normalized = _nested_table_representation(cell)
    return [
        cell.tag,
        attribute_bindings(
            cell, omitted_attributes=() if include_styles else (xml_names.TABLE_STYLE_NAME,)
        ),
        _attributes(cell, "unused", include_styles=include_styles),
        visible_words(normalized),
        protected_xml(
            normalized,
            omitted_elements=(xml_names.SVG_TITLE, xml_names.SVG_DESC),
            omitted_root_attributes=() if include_styles else (xml_names.TABLE_STYLE_NAME,),
            omitted_element_attributes={
                qn(ns, "a"): (xml_names.OFFICE_TITLE,) for ns in ("draw", "text")
            },
        ),
    ]


def _nested_table_representation(cell: etree._Element) -> etree._Element:
    clone = etree.Element(cell.tag, nsmap=cell.nsmap)
    clone.attrib.update(cell.attrib)
    clone.text, clone.tail = cell.text, cell.tail
    clone.extend(deepcopy(child) for child in cell)
    for table in reversed(list(clone.iter(xml_names.TABLE_TABLE))):
        _unwrap_headers(table)
        for parent in table.iter():
            owner = (
                parent
                if parent is table
                else next(parent.iterancestors(xml_names.TABLE_TABLE), None)
            )
            if owner is table:
                _coalesce(parent)
    return clone


def _unwrap_headers(table: etree._Element) -> None:
    for wrapper in list(
        table.iter(xml_names.TABLE_TABLE_HEADER_ROWS, xml_names.TABLE_TABLE_HEADER_COLUMNS)
    ):
        owner = next(wrapper.iterancestors(xml_names.TABLE_TABLE), None)
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
        if child.tag not in {xml_names.TABLE_TABLE_ROW, xml_names.TABLE_TABLE_COLUMN}:
            previous = None
            continue
        attribute = (
            "number-rows-repeated"
            if child.tag == xml_names.TABLE_TABLE_ROW
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
        omitted_elements=(xml_names.SVG_TITLE, xml_names.SVG_DESC),
        omitted_element_attributes={
            qn(ns, "a"): (xml_names.OFFICE_TITLE,) for ns in ("draw", "text")
        },
    )
