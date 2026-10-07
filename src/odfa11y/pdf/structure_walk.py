# SPDX-License-Identifier: MPL-2.0
"""Walk the PDF structure tree into nodes with resolved standard roles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pypdf.errors import PdfReadError
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, NameObject

if TYPE_CHECKING:
    from collections.abc import Iterator

STANDARD_STRUCTURE_TYPES = {
    "Document",
    "Part",
    "Art",
    "Sect",
    "Div",
    "BlockQuote",
    "Caption",
    "TOC",
    "TOCI",
    "Index",
    "NonStruct",
    "Private",
    "P",
    "H",
    "H1",
    "H2",
    "H3",
    "H4",
    "H5",
    "H6",
    "L",
    "LI",
    "Lbl",
    "LBody",
    "Table",
    "TR",
    "TH",
    "TD",
    "THead",
    "TBody",
    "TFoot",
    "Span",
    "Quote",
    "Note",
    "Reference",
    "BibEntry",
    "Code",
    "Link",
    "Annot",
    "Ruby",
    "Warichu",
    "Figure",
    "Formula",
    "Form",
}


def pdf_dictionary(value: object) -> DictionaryObject:
    """Resolve an optional direct or indirect PDF dictionary.

    Returns
    -------
    DictionaryObject
        The resolved dictionary, or an empty dictionary when the value is absent.

    Raises
    ------
    PdfReadError
        A present value is not a dictionary.

    """
    if isinstance(value, IndirectObject):
        value = value.get_object()
    if value is None:
        return DictionaryObject()
    if not isinstance(value, DictionaryObject):
        msg = "Expected a PDF dictionary"
        raise PdfReadError(msg)
    return value


@dataclass(slots=True)
class StructureNode:
    """A structure element with its declared tag, resolved standard role and children."""

    tag: str
    role: str | None
    element: DictionaryObject
    children: list[StructureNode] = field(default_factory=list)
    object_references: int = 0

    def walk(self) -> Iterator[StructureNode]:
        """Yield this node and its descendants in document order.

        Yields
        ------
        StructureNode
            The nodes in preorder.

        """
        pending: list[StructureNode] = [self]
        while pending:
            node = pending.pop()
            yield node
            pending.extend(reversed(node.children))


def role_map_of(root: DictionaryObject) -> dict[str, str]:
    """Read the ``/RoleMap`` of a structure tree root.

    Returns
    -------
    dict[str, str]
        Custom tag to mapped tag, without leading slashes.

    """
    return {
        str(key).removeprefix("/"): str(value).removeprefix("/")
        for key, value in pdf_dictionary(root.get("/RoleMap")).items()
    }


def build_tree(root: DictionaryObject) -> StructureNode:
    """Build the structure hierarchy, visiting each dictionary once.

    Returns
    -------
    StructureNode
        A synthetic root whose children are the top-level structure elements.

    """
    role_map = role_map_of(root)
    top = StructureNode("StructTreeRoot", "StructTreeRoot", root)
    seen: set[int] = set()
    pending: list[tuple[object, StructureNode]] = [(root.get("/K"), top)]
    while pending:
        kids, parent = pending.pop()
        for value in _children(kids, seen):
            tag = value.get("/S")
            if isinstance(tag, NameObject):
                name = str(tag).removeprefix("/")
                node = StructureNode(name, resolve_role(name, role_map), value)
                parent.children.append(node)
                pending.append((value.get("/K"), node))
            elif value.get("/Type") == "/OBJR":
                parent.object_references += 1
    return top


def _children(kids: object, seen: set[int]) -> Iterator[DictionaryObject]:
    stack = [kids]
    while stack:
        value = stack.pop()
        if isinstance(value, IndirectObject):
            value = value.get_object()
        if isinstance(value, ArrayObject | DictionaryObject):
            if id(value) in seen:
                continue
            seen.add(id(value))
        if isinstance(value, ArrayObject):
            stack.extend(reversed(value))
        elif isinstance(value, DictionaryObject):
            yield value


def resolve_role(name: str, role_map: dict[str, str]) -> str | None:
    """Resolve a tag to a standard structure type through the role map.

    Returns
    -------
    str | None
        The standard type, or None when the chain is cyclic or unmapped.

    """
    seen: set[str] = set()
    while name not in STANDARD_STRUCTURE_TYPES:
        if name in seen or name not in role_map:
            return None
        seen.add(name)
        name = role_map[name]
    return name
