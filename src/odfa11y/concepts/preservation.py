# SPDX-License-Identifier: MPL-2.0
"""Preserve opaque package resources and flat embedded binary content across source edits."""

import hashlib
from copy import deepcopy
from dataclasses import dataclass

from lxml import etree

from odfa11y.errors import XmlParseError
from odfa11y.odf import PackageStorage, Part
from odfa11y.odf import names as xml_names
from odfa11y.odf.allowance import (
    Allowance,
    Attributes,
    Container,
    Created,
    Permission,
    Removed,
    RepeatedStructure,
    Text,
    Wrapped,
)
from odfa11y.odf.canonical import protected_xml
lazy from odfa11y.odf import OdfDocument


def opaque_payloads(document: OdfDocument) -> tuple[tuple[str, str], ...]:
    """Snapshot resources that accessibility operations never rewrite.

    Returns
    -------
    tuple[tuple[str, str], ...]
        Opaque member and embedded-data identities with content digests.

    """
    facts = []
    if isinstance(document.storage, PackageStorage):
        editable = {document.member_name(part) for part in Part}
        facts.extend(
            (name, hashlib.sha256(document.storage.read(name)).hexdigest())
            for name in document.storage.member_names()
            if name not in editable
        )
    for index, node in enumerate(document.tree(Part.CONTENT).iter(xml_names.OFFICE_BINARY_DATA)):
        value = "".join("".join(node.itertext()).split()).encode()
        facts.append((f"embedded[{index}]", hashlib.sha256(value).hexdigest()))
    return tuple(facts)


@dataclass(frozen=True, slots=True)
class _Tree:
    root: etree._Element
    nodes: tuple[etree._Element, ...]
    parts: frozenset[Part]


@dataclass(frozen=True, slots=True)
class ProtectedPackage:
    """A stable view of every XML part and opaque member before or after edits."""

    trees: dict[str, _Tree]
    unparsed: tuple[tuple[str, bytes], ...]

    @classmethod
    def capture(cls, document: OdfDocument) -> ProtectedPackage:
        grouped: dict[str, set[Part]] = {}
        for part in Part:
            if (name := document.member_name(part)) is not None:
                grouped.setdefault(name, set()).add(part)
        trees = {}
        unparsed = []
        for name, parts in grouped.items():
            try:
                root = document.tree(next(iter(parts))).getroot()
            except XmlParseError:
                unparsed.append((name, document.storage.read(name)))
            else:
                trees[name] = _Tree(deepcopy(root), tuple(root.iter()), frozenset(parts))
        return cls(trees, tuple(sorted(unparsed)))

    def masked(self, allowance: Allowance) -> tuple[tuple[str, str], ...] | None:
        facts = []
        for name, tree in self.trees.items():
            try:
                result = _masked_tree(tree, allowance)
            except _InvalidAllowance, ValueError:
                return None
            if result is not None:
                facts.append((name, protected_xml(result)))
        return tuple(sorted(facts))

    def preserved(self, after: ProtectedPackage, allowance: Allowance) -> bool:
        if not _valid_lifetimes(self, after, allowance):
            return False
        before = self.masked(allowance)
        return (
            before is not None
            and self.unparsed == after.unparsed
            and before == after.masked(allowance)
        )


def _valid_lifetimes(
    before: ProtectedPackage, after: ProtectedPackage, allowance: Allowance
) -> bool:
    original = {node for tree in before.trees.values() for node in tree.nodes}
    current = {node for tree in after.trees.values() for node in tree.nodes}
    for permission in allowance.permissions:
        if isinstance(permission, (Created, Container, Wrapped)) and permission.node in original:
            return False
        if isinstance(permission, Removed) and permission.node in current:
            return False
    return True


def _remove(node: etree._Element) -> None:
    if (parent := node.getparent()) is not None:
        parent.remove(node)


def _unwrap(node: etree._Element) -> None:
    if (parent := node.getparent()) is None:
        return
    value = (node.text or "") + (node.tail or "")
    previous = node.getprevious()
    if previous is None:
        parent.text = (parent.text or "") + value
    else:
        previous.tail = (previous.tail or "") + value
    parent.remove(node)


def _normalize_repeated(root: etree._Element, permission: RepeatedStructure) -> None:
    for node in list(root.iter()):
        if node.tag not in permission.wrappers or _owner(node, str(root.tag)) is not root:
            continue
        if (parent := node.getparent()) is None:
            continue
        position = parent.index(node)
        for child in list(node):
            parent.insert(position, child)
            position += 1
        parent.remove(node)
    for parent in root.iter():
        if parent is root or _owner(parent, str(root.tag)) is root:
            _coalesce(parent, dict(permission.repetitions))


def _coalesce(parent: etree._Element, repeats: dict[str, str]) -> None:
    previous = None
    for child in list(parent):
        attribute = repeats.get(str(child.tag))
        if attribute is None:
            previous = None
            continue
        count = str(int(child.attrib.pop(attribute, "1")))
        if child.tail and not child.tail.strip():
            child.tail = None
        if previous is not None and previous.tag == child.tag:
            old = previous.attrib.pop(attribute, "1")
            equal = protected_xml(previous) == protected_xml(child)
            previous.set(attribute, old)
            if equal:
                previous.set(attribute, str(int(old) + int(count)))
                parent.remove(child)
                continue
        child.set(attribute, count)
        previous = child


def _owner(node: etree._Element, tag: str) -> etree._Element | None:
    return next(node.iterancestors(tag), None)


class _InvalidAllowance(Exception):
    pass


def _masked_tree(tree: _Tree, allowance: Allowance) -> etree._Element | None:
    root = deepcopy(tree.root)
    nodes = dict(zip(tree.nodes, root.iter(), strict=True))
    permissions = [p for p in allowance.permissions if p.part in tree.parts]
    for permission in permissions:
        node = nodes.get(permission.node)
        if node is not None and not _mask_node(node, permission):
            raise _InvalidAllowance
    containers = sorted(
        (p for p in permissions if isinstance(p, Container)),
        key=lambda p: len(tuple(p.node.iterancestors())),
        reverse=True,
    )
    for permission in containers:
        if not isinstance(permission, Container) or (node := nodes.get(permission.node)) is None:
            continue
        empty = not len(node) and not (node.text or "").strip()
        if not empty or dict(node.attrib) != dict(permission.attributes):
            raise _InvalidAllowance
        if node is root:
            return None
        _remove(node)
    return root


def _mask_node(node: etree._Element, permission: Permission) -> bool:
    match permission:
        case Attributes(names=names):
            for attribute in names:
                node.attrib.pop(attribute, None)
        case Text():
            node.text = None
        case Removed():
            _remove(node)
        case Created() | Wrapped():
            return _mask_creation(node, permission)
        case RepeatedStructure():
            _normalize_repeated(node, permission)
        case Container():
            pass
    return True


def _mask_creation(node: etree._Element, permission: Created | Wrapped) -> bool:
    if protected_xml(node) != permission.expected:
        return False
    if isinstance(permission, Wrapped):
        if len(node):
            return False
        _unwrap(node)
    else:
        _remove(node)
    return True
