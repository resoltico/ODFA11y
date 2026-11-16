# SPDX-License-Identifier: MPL-2.0
"""Walk the PDF structure tree into nodes with resolved standard roles."""

from dataclasses import dataclass, field
lazy from collections.abc import Iterator

from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    IndirectObject,
    NameObject,
    NumberObject,
    StreamObject,
)

from odfa11y.errors import ToolFailure
from odfa11y.pdf.reading.objects import dictionary, xref

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
    stream_xref: int | None = None

    @property
    def identity(self) -> tuple[int | None, int | None]:
        """Page stream or independent Form stream ownership scope."""
        return (self.page_xref if self.stream_xref is None else None, self.stream_xref)


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
        for key, value in dictionary(root.get("/RoleMap")).items()
    }


def build_tree(root: DictionaryObject, limit: int) -> StructureNode:
    """Build the structure hierarchy, visiting each dictionary once.

    Returns
    -------
    StructureNode
        A synthetic root whose children are the top-level structure elements.

    Elements and their kids together count toward the supplied traversal limit; more raise
    ``ToolFailure``.

    """
    role_map = role_map_of(root)
    top = StructureNode("StructTreeRoot", "StructTreeRoot", root)
    seen: set[int] = set()
    nodes = 0
    work = [0]
    pending: list[tuple[object, StructureNode]] = [(root.get("/K"), top)]
    while pending:
        kids, parent = pending.pop()
        for value in _children(kids, work, limit):
            nodes += 1
            _count(nodes, limit)
            if isinstance(value, DictionaryObject) and isinstance(value.get("/S"), NameObject):
                if id(value) in seen:
                    continue
                seen.add(id(value))
                name = str(value["/S"]).removeprefix("/")
                page = xref(value.get("/Pg"))
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
    """Record a marked-content or object reference kid on its structure element.

    Raises
    ------
    ToolFailure
        A stream reference has an unsupported shape.

    """
    if isinstance(kid, int):
        parent.marked_content.append(MarkedContentReference(int(kid), parent.page_xref))
        return
    page = xref(kid.get("/Pg"))
    page = page if page is not None else parent.page_xref
    kind = kid.get("/Type")
    mcid = kid.get("/MCID")
    if kind == "/MCR" and isinstance(mcid, NumberObject):
        stream = kid.get("/Stm")
        if stream is not None and (
            not isinstance(stream, IndirectObject)
            or not isinstance(stream.get_object(), StreamObject)
        ):
            msg = "Cannot inspect a malformed /Stm content reference"
            raise ToolFailure(msg)
        parent.marked_content.append(MarkedContentReference(int(mcid), page, xref(stream)))
    elif kind == "/OBJR":
        parent.object_references.append(ObjectReference(xref(kid.get("/Obj")), page))


def _count(nodes: int, limit: int) -> None:
    if nodes > limit:
        msg = f"Structure tree has more than {limit} elements"
        raise ToolFailure(msg)


def _children(kids: object, work: list[int], limit: int) -> Iterator[DictionaryObject | int]:
    stack: list[tuple[object, bool]] = [(kids, False)]
    active: set[int] = set()
    while stack:
        value, leaving = stack.pop()
        if leaving:
            active.remove(id(value))
            continue
        work[0] += 1
        _count(work[0], limit)
        if isinstance(value, IndirectObject):
            value = value.get_object()
        if isinstance(value, ArrayObject):
            if id(value) in active:
                continue
            _count(work[0] + len(value), limit)
            active.add(id(value))
            stack.append((value, True))
            stack.extend((child, False) for child in reversed(value))
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
