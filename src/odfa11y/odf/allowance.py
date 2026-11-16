# SPDX-License-Identifier: MPL-2.0
"""Explicit XML permissions returned by an edit, independent of decision dispatch."""

from copy import deepcopy
from dataclasses import dataclass, field

from lxml import etree

from odfa11y.odf.canonical import protected_xml
from odfa11y.targets import Part


@dataclass(frozen=True, slots=True)
class Attributes:
    part: Part
    node: etree._Element
    names: frozenset[str]


@dataclass(frozen=True, slots=True)
class Text:
    part: Part
    node: etree._Element


@dataclass(frozen=True, slots=True)
class Removed:
    part: Part
    node: etree._Element


@dataclass(frozen=True, slots=True)
class Created:
    part: Part
    node: etree._Element
    expected: str
    style_name: str | None = None

    @classmethod
    def of(cls, part: Part, node: etree._Element, *, style_name: str | None = None) -> Created:
        return cls(part, node, protected_xml(node), style_name)


@dataclass(frozen=True, slots=True)
class Container:
    """A newly created container, removable only after its permitted children are masked."""

    part: Part
    node: etree._Element
    attributes: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class Wrapped:
    """A newly inserted plain text wrapper; unwrapping must retain every character."""

    part: Part
    node: etree._Element
    expected: str


@dataclass(frozen=True, slots=True)
class RepeatedStructure:
    """Header wrappers and repeated runs within one explicit table, excluding nested tables."""

    part: Part
    node: etree._Element
    wrappers: frozenset[str]
    repetitions: tuple[tuple[str, str], ...]
    created: tuple[etree._Element, ...] = ()


type Permission = Attributes | Text | Removed | Created | Container | Wrapped | RepeatedStructure


@dataclass(frozen=True, slots=True)
class Allowance:
    permissions: tuple[Permission, ...] = ()

    def __or__(self, other: Allowance) -> Allowance:
        return Allowance(self.permissions + other.permissions)

    @property
    def created_styles(self) -> frozenset[str]:
        return frozenset(
            permission.style_name
            for permission in self.permissions
            if isinstance(permission, Created) and permission.style_name is not None
        )


@dataclass(frozen=True, slots=True)
class TextFields:
    """Capture supplied scalar child fields before an edit creates or updates them."""

    part: Part
    parent: etree._Element
    fields: tuple[tuple[str, str, etree._Element | None], ...]

    @classmethod
    def capture(
        cls, part: Part, parent: etree._Element, values: tuple[tuple[str, str | None], ...]
    ) -> TextFields:
        return cls(
            part,
            parent,
            tuple((tag, value, parent.find(tag)) for tag, value in values if value is not None),
        )

    def allowance(self) -> Allowance:
        permissions: list[Permission] = []
        for tag, value, original in self.fields:
            if original is not None:
                permissions.append(Text(self.part, original))
            elif (node := self.parent.find(tag)) is not None:
                expected = deepcopy(node)
                expected.attrib.clear()
                for child in list(expected):
                    expected.remove(child)
                expected.text = value
                expected.tail = None
                permissions.append(Created(self.part, node, protected_xml(expected)))
        return Allowance(tuple(permissions))


@dataclass(frozen=True, slots=True)
class XmlChange:
    changed: bool
    allowance: Allowance = field(default_factory=Allowance)
