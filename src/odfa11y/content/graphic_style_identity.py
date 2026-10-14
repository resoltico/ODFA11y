# SPDX-License-Identifier: MPL-2.0
"""Resolve graphic roles and derive isolated, verifiable role styles."""

from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy
from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.odf import NS, Part, qn

from .xml import protected_xml

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument

from .graphic_styles import ROLE, GraphicStyles

PREFIX = "ODFA11yRole_"
STYLE_ATTRIBUTES = tuple(
    qn(ns, key) for ns in ("draw", "presentation") for key in ("style-name", "class-names")
)


def normalized_role_attributes(document: OdfDocument, shape: etree._Element) -> dict[str, str]:
    """Recover original references only after proving the generated style's derivation.

    Returns
    -------
    dict[str, str]
        Original style references only when the role derivation is proven.

    """
    attrs = {attr: shape.get(attr, "") for attr in STYLE_ATTRIBUTES if shape.get(attr) is not None}
    generated = [
        token for value in attrs.values() for token in value.split() if token.startswith(PREFIX)
    ]
    if len(generated) != 1:
        return attrs
    try:
        return _proven_role_attributes(document, shape, attrs, generated[0])
    except ValueError, KeyError, TypeError:
        return attrs


def _proven_role_attributes(
    document: OdfDocument, shape: etree._Element, attrs: dict[str, str], name: str
) -> dict[str, str]:
    encoded = name.removeprefix(PREFIX).rsplit("_", 1)[0]
    original = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    if not isinstance(original, dict) or any(
        k not in STYLE_ATTRIBUTES or not isinstance(v, str) for k, v in original.items()
    ):
        return attrs
    shadow = deepcopy(shape)
    for attr in STYLE_ATTRIBUTES:
        shadow.attrib.pop(attr, None)
    shadow.attrib.update(original)
    catalog = GraphicStyles(document)
    ns, family, names = catalog.context(shadow)
    expected = (
        deepcopy(catalog.style(family, names[-1])) if names else etree.Element(qn("style", "style"))
    )
    expected.set(qn("style", "name"), name)
    expected.set(qn("style", "family"), family)
    generated = catalog.automatic.get((family, name), [])
    if len(generated) != 1:
        return attrs
    properties = generated[0].findall("style:graphic-properties", NS)
    if len(properties) != 1 or properties[0].get(ROLE) not in {"true", "false"}:
        return attrs
    if document.tree(Part.CONTENT).getroot().get(qn("office", "version")) != "1.4":
        return attrs
    actual = deepcopy(generated[0])
    for node in (expected, actual):
        props = node.find("style:graphic-properties", NS)
        if props is not None:
            props.attrib.pop(ROLE, None)
            if not props.attrib and not len(props):
                node.remove(props)
    applied = dict(original)
    attribute = (
        qn(ns, "class-names") if original.get(qn(ns, "class-names")) else qn(ns, "style-name")
    )
    applied[attribute] = (
        (original.get(attribute, "") + " " + name).strip()
        if attribute.endswith("class-names")
        else name
    )
    if attrs == applied and _style_signature(actual) == _style_signature(expected):
        return original
    return attrs


def normalized_graphic_tree(document: OdfDocument, root: etree._Element) -> etree._Element:
    """Copy content, restoring only proven role derivations to original references.

    Returns
    -------
    etree._Element
        A copy with proven style references restored.

    """
    clone = deepcopy(root)
    for source, target in zip(root.iter(), clone.iter(), strict=True):
        if any(source.get(attr) is not None for attr in STYLE_ATTRIBUTES):
            attributes = normalized_role_attributes(document, source)
            for attr in STYLE_ATTRIBUTES:
                target.attrib.pop(attr, None)
            target.attrib.update(attributes)
    return clone


def graphic_style_fingerprint(document: OdfDocument, shape: etree._Element) -> str:
    """Bind referenced style definitions and default visual properties.

    Returns
    -------
    str
        A digest that changes when authored style properties change.

    """
    catalog = GraphicStyles(document)
    shadow = normalized_graphic_tree(document, shape)
    try:
        return _style_facts(catalog, shadow)
    except ValueError as error:
        return str(error)


def _style_facts(catalog: GraphicStyles, shadow: etree._Element) -> str:
    _ns, family, names = catalog.context(shadow)
    facts = [protected_xml(style) for style in catalog.defaults.get(family, [])]
    for source_name in names:
        name = source_name
        style = catalog.style(family, name)
        seen: set[etree._Element] = set()
        while style not in seen:
            seen.add(style)
            facts.append(protected_xml(style))
            parent = style.get(qn("style", "parent-style-name"))
            if not parent:
                break
            style = catalog.style(family, parent, common=True)
    return hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()[:16]


def _style_signature(style: etree._Element) -> list[object]:
    return [
        (
            node.tag,
            len(node),
            sorted(node.attrib.items()),
            node.text,
            node.tail,
            [
                (
                    attribute,
                    [
                        (prefix, uri)
                        for prefix, uri in node.nsmap.items()
                        if prefix and f"{prefix}:" in value
                    ],
                )
                for attribute, value in sorted(node.attrib.items())
            ],
        )
        for node in style.iter()
    ]
