# SPDX-License-Identifier: AGPL-3.0-only
"""Describe declared database objects without opening connections or changing bindings."""

import re

lazy from lxml import etree

from odfa11y.concepts import protected_xml
from odfa11y.decisions import Decision
from odfa11y.decisions.answers import DatabaseDescriptionAnswer
from odfa11y.decisions.domain import resolved_node
from odfa11y.decisions.edit import EditResult, Outcome, Status
from odfa11y.odf import Part, qn, select_elements
from odfa11y.odf import names as xml_names
from odfa11y.odf.allowance import Allowance, Attributes
from odfa11y.report import Location
from odfa11y.targets import Fingerprint
lazy from odfa11y.odf import OdfDocument

OBJECTS = {
    qn("db", name)
    for name in (
        "query",
        "query-collection",
        "component",
        "component-collection",
        "column",
        "table-representation",
    )
}
ORDINAL = re.compile(r"\[[0-9]+\]")


def targets(document: OdfDocument) -> dict[str, list[etree._Element]]:
    """Index described objects by hierarchical logical name/ordinal paths.

    Returns
    -------
    dict[str, list[etree._Element]]
        Every declaration for each target; duplicates remain visible for rejection.

    """
    result: dict[str, list[etree._Element]] = {}
    positions: dict[etree._Element, dict[etree._Element, int]] = {}
    roots = select_elements(document.tree(Part.CONTENT), "//office:body/office:database")
    if not roots:
        return result
    for node in roots[0].iter():
        if node.tag in OBJECTS or _form_target(node):
            result.setdefault(_path(node, positions), []).append(node)
    return result


def description_attribute(node: etree._Element) -> str:
    """Choose the standard description field for one declared object.

    Returns
    -------
    str
        ``db:description`` or a form control's ``form:title``.

    """
    return xml_names.FORM_TITLE if _form_target(node) else xml_names.DB_DESCRIPTION


def fingerprint(node: etree._Element) -> Fingerprint:
    """Bind the description decision to SQL, bindings and all other object content.

    Returns
    -------
    str
        A reviewed digest excluding only the object's description.

    """
    return Fingerprint.from_digest(
        protected_xml(node, omitted_element_attributes=description_attributes(node))
    )


def description_attributes(root: etree._Element) -> dict[str, tuple[str, ...]]:
    """Declare precisely the editable description attributes within a target subtree.

    Returns
    -------
    dict[str, tuple[str, ...]]
        Standard object attributes, including independently described descendants.

    """
    attributes: dict[str, tuple[str, ...]] = {tag: (xml_names.DB_DESCRIPTION,) for tag in OBJECTS}
    for node in root.iter():
        if _form_target(node):
            attributes[str(node.tag)] = (xml_names.FORM_TITLE,)
    return attributes


def _form_target(node: etree._Element) -> bool:
    return (
        isinstance(node.tag, str)
        and node.tag.startswith(xml_names.FORM_)
        and bool(node.get(xml_names.FORM_NAME))
    )


def _path(node: etree._Element, positions: dict[etree._Element, dict[etree._Element, int]]) -> str:
    parts = []
    for item in reversed([node, *node.iterancestors()]):
        if item.tag not in OBJECTS and not _form_target(item):
            continue
        kind = str(item.tag).rpartition("}")[2]
        name = item.get(xml_names.DB_NAME) or item.get(xml_names.FORM_NAME)
        segment = (
            Location.named("content", kind, name).path
            if name
            else Location.indexed("content", kind, _ordinal(item, positions)).path
        )
        parts.append(segment.removeprefix("content/"))
    return "content/" + "/".join(parts)


def _ordinal(
    node: etree._Element, positions: dict[etree._Element, dict[etree._Element, int]]
) -> int:
    parent = node.getparent()
    if parent is None:
        return 1
    if parent not in positions:
        counts: dict[object, int] = {}
        siblings = {}
        for child in parent:
            counts[child.tag] = counts.get(child.tag, 0) + 1
            siblings[child] = counts[child.tag]
        positions[parent] = siblings
    return positions[parent][node]


def edit_description(
    document: OdfDocument, decision: Decision[DatabaseDescriptionAnswer]
) -> EditResult:
    """Set a supplied description while preserving connections, SQL and object content."""
    node = resolved_node(document, decision)
    attribute = description_attribute(node)
    allowance = Allowance((
        Attributes(Part.CONTENT, node, frozenset({description_attribute(node)})),
    ))
    value = decision.answer.text.strip()
    changed = node.get(attribute) != value
    if changed:
        node.set(attribute, value)
    return EditResult(
        (
            Outcome(
                decision.kind.id,
                Status.APPLIED if changed else Status.UNCHANGED,
                "Applied database object description."
                if changed
                else "Database object description already matches.",
                target=decision.target_path,
                count=int(changed),
            ),
        ),
        allowance,
    )
