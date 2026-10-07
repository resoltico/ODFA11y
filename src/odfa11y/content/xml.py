# SPDX-License-Identifier: MPL-2.0
"""Digest protected XML while a family declares exactly which metadata it may edit."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import TYPE_CHECKING

from lxml import etree

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping


def protected_xml(
    element: etree._Element,
    *,
    omitted_elements: Collection[str] = (),
    omitted_root_attributes: Collection[str] = (),
    omitted_element_attributes: Mapping[str, Collection[str]] | None = None,
) -> str:
    """Hash all structure, references and content outside explicitly editable metadata.

    Returns
    -------
    str
        A full SHA-256 of the canonical protected XML.

    """
    copy = deepcopy(element)
    attributes_by_tag = omitted_element_attributes or {}
    for node in list(copy.iter()):
        excluded = attributes_by_tag.get(str(node.tag), ())
        if node is copy:
            excluded = (*excluded, *omitted_root_attributes)
        for attribute in excluded:
            node.attrib.pop(attribute, None)
        if node.tag in omitted_elements:
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
            continue
    # A copy loses inherited bindings used only in values. Capture those from the source.
    bindings = []
    for node in element.iter():
        if node.tag in omitted_elements or any(
            parent.tag in omitted_elements for parent in node.iterancestors()
        ):
            continue
        excluded = attributes_by_tag.get(str(node.tag), ())
        if node is element:
            excluded = (*excluded, *omitted_root_attributes)
        if namespaces := attribute_bindings(node, omitted_attributes=excluded):
            bindings.append((str(node.tag), namespaces))
    # Exclusive canonicalization ignores unused bindings introduced by metadata edits.
    canonical = etree.tostring(copy, method="c14n", exclusive=True)
    digest = hashlib.sha256(canonical)
    digest.update(json.dumps(bindings, sort_keys=True).encode())
    return digest.hexdigest()


def attribute_bindings(
    element: etree._Element, *, omitted_attributes: Collection[str] = ()
) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    """Record in-scope bindings on which attribute values may depend.

    Returns
    -------
    tuple[tuple[str, tuple[tuple[str, str], ...]], ...]
        Attribute names and their used prefixes/default namespace, in stable order.

    """
    facts = []
    for attribute, value in sorted(element.attrib.items()):
        if attribute in omitted_attributes:
            continue
        bindings = tuple(
            sorted(
                (prefix or "", uri)
                for prefix, uri in element.nsmap.items()
                if uri and (prefix is None or f"{prefix}:" in value)
            )
        )
        if bindings:
            facts.append((attribute, bindings))
    return tuple(facts)
