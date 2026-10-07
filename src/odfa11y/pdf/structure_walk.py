# SPDX-License-Identifier: MPL-2.0
"""Walk the PDF structure tree into nodes with resolved standard roles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pypdf.errors import PdfReadError
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    IndirectObject,
    NameObject,
    NumberObject,
)

from odfa11y.errors import ToolFailedError
from odfa11y.pdf_limits import MAX_STRUCTURE_NODES

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


@dataclass(frozen=True, slots=True)
class ObjectReference:
    """An ``/OBJR`` kid: the referenced object and the page it is declared on."""

    object_xref: int | None
    page_xref: int | None


@dataclass(frozen=True, slots=True)
class MarkedContentReference:
    """A marked-content reference kid: the MCID and the page whose content stream holds it."""

    mcid: int
    page_xref: int | None


@dataclass(slots=True)
class StructureNode:
    """A structure element with its tag, resolved role, effective page and children."""

    tag: str
    role: str | None
    element: DictionaryObject
    page_xref: int | None = None
    children: list[StructureNode] = field(default_factory=list)
    object_references: list[ObjectReference] = field(default_factory=list)
    marked_content: list[MarkedContentReference] = field(default_factory=list)

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

    Elements and their kids together count toward ``MAX_STRUCTURE_NODES``; more raise
    ``ToolFailedError``.

    """
    role_map = role_map_of(root)
    top = StructureNode("StructTreeRoot", "StructTreeRoot", root)
    seen: set[int] = set()
    nodes = 0
    pending: list[tuple[object, StructureNode]] = [(root.get("/K"), top)]
    while pending:
        kids, parent = pending.pop()
        for value in _children(kids, seen):
            nodes += 1
            _count(nodes)
            if isinstance(value, DictionaryObject) and isinstance(value.get("/S"), NameObject):
                name = str(value["/S"]).removeprefix("/")
                page = _xref(value.get("/Pg"))
                node = StructureNode(
                    name,
                    resolve_role(name, role_map),
                    value,
                    page if page is not None else parent.page_xref,
                )
                parent.children.append(node)
                pending.append((value.get("/K"), node))
            else:
                _add_reference(parent, value)
    return top


def _add_reference(parent: StructureNode, kid: DictionaryObject | int) -> None:
    """Record a marked-content or object reference kid on its structure element."""
    if isinstance(kid, int):
        parent.marked_content.append(MarkedContentReference(int(kid), parent.page_xref))
        return
    page = _xref(kid.get("/Pg"))
    page = page if page is not None else parent.page_xref
    kind = kid.get("/Type")
    mcid = kid.get("/MCID")
    if kind == "/MCR" and isinstance(mcid, NumberObject) and kid.get("/Stm") is None:
        parent.marked_content.append(MarkedContentReference(int(mcid), page))
    elif kind == "/OBJR":
        parent.object_references.append(ObjectReference(_xref(kid.get("/Obj")), page))


def _count(nodes: int) -> None:
    if nodes > MAX_STRUCTURE_NODES:
        msg = f"Structure tree has more than {MAX_STRUCTURE_NODES} elements"
        raise ToolFailedError(msg)


def _xref(value: object) -> int | None:
    return value.idnum if isinstance(value, IndirectObject) else None


def _children(kids: object, seen: set[int]) -> Iterator[DictionaryObject | int]:
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
        elif isinstance(value, DictionaryObject | NumberObject):
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
