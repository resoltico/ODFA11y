# SPDX-License-Identifier: MPL-2.0
"""Build small synthetic PDFs: tagged structure trees, and text pages with links."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from pypdf import PageObject
    from pypdf.generic import IndirectObject

Spec = str | tuple[str, "Sequence[Spec]"]


def _font() -> DictionaryObject:
    return DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })


def _write_text(writer: PdfWriter, page: PageObject, lines: Sequence[str], y: float) -> None:
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): _font()})
    })
    operations = [
        f"BT /F1 12 Tf 10 {y - 16 * index} Td ({line}) Tj ET" for index, line in enumerate(lines)
    ]
    content = DecodedStreamObject()
    content.set_data("\n".join(operations).encode())
    page[NameObject("/Contents")] = writer._add_object(content)


def _add_element(
    writer: PdfWriter, spec: Spec, parent: IndirectObject, role_alt: str | None
) -> IndirectObject:
    tag, children = (spec, ()) if isinstance(spec, str) else spec
    element = DictionaryObject({
        NameObject("/Type"): NameObject("/StructElem"),
        NameObject("/S"): NameObject(f"/{tag}"),
        NameObject("/P"): parent,
    })
    reference = writer._add_object(element)
    if children:
        element[NameObject("/K")] = ArrayObject([
            _add_element(writer, child, reference, role_alt) for child in children
        ])
    else:
        element[NameObject("/K")] = NumberObject(0)
    if role_alt is not None and tag in {"Figure", "Illustration"}:
        element[NameObject("/Alt")] = TextStringObject(role_alt)
    return reference


def tagged_writer(
    structure: Sequence[Spec] = ("H1",),
    *,
    role_map: dict[str, str] | None = None,
    figure_alt: str | None = None,
    link_annotations: int = 0,
) -> PdfWriter:
    """Create a one-page PDF with every marker the audit looks for and a given structure tree.

    Returns
    -------
    PdfWriter
        A writer; each ``structure`` entry is a tag or ``(tag, children)``.

    """
    writer = PdfWriter()
    page = writer.add_blank_page(width=100, height=100)
    writer.add_metadata({"/Title": "Synthetic PDF"})
    root = writer.root_object
    root[NameObject("/Lang")] = TextStringObject("en-GB")
    root[NameObject("/MarkInfo")] = DictionaryObject({
        NameObject("/Marked"): BooleanObject(value=True)
    })
    writer.create_viewer_preferences()[NameObject("/DisplayDocTitle")] = BooleanObject(value=True)
    metadata = DecodedStreamObject()
    metadata.set_data(
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/" xmlns:ua="http://www.aiim.org/pdfua/ns/id/">'
        b"<ua:part>1</ua:part></x:xmpmeta>"
    )
    metadata[NameObject("/Type")] = NameObject("/Metadata")
    metadata[NameObject("/Subtype")] = NameObject("/XML")
    root[NameObject("/Metadata")] = writer._add_object(metadata)
    tree = DictionaryObject({NameObject("/Type"): NameObject("/StructTreeRoot")})
    reference = writer._add_object(tree)
    tree[NameObject("/K")] = ArrayObject([
        _add_element(writer, spec, reference, figure_alt) for spec in structure
    ])
    if role_map:
        tree[NameObject("/RoleMap")] = DictionaryObject({
            NameObject(f"/{key}"): NameObject(f"/{value}") for key, value in role_map.items()
        })
    root[NameObject("/StructTreeRoot")] = reference
    _write_text(writer, page, ["Synthetic text"], 50)
    if link_annotations:
        page[NameObject("/Annots")] = ArrayObject([
            writer._add_object(_link_annotation("https://example.test/a", 10, 40))
            for _ in range(link_annotations)
        ])
    return writer


def link_elements(writer: PdfWriter) -> list[IndirectObject]:
    """List the Link structure elements of a synthetic PDF in tree order.

    Returns
    -------
    list[IndirectObject]
        References to every structure element tagged ``Link``.

    """
    found: list[IndirectObject] = []
    pending: list[Any] = [writer.root_object["/StructTreeRoot"]]
    while pending:
        reference = pending.pop()
        element = reference.get_object()
        if element.get("/S") == "/Link":
            found.append(reference)
        kids = element.get("/K")
        if isinstance(kids, ArrayObject):
            pending.extend(reversed([kid for kid in kids if hasattr(kid, "get_object")]))
    return found


def map_link(
    writer: PdfWriter,
    element: IndirectObject,
    annotation: IndirectObject,
    *,
    page: IndirectObject | None = None,
) -> None:
    """Add an ``/OBJR`` kid to a structure element that refers to an annotation.

    ``page`` defaults to the first page; pass another page to declare a wrong one.
    """
    owner = page if page is not None else writer.pages[0].indirect_reference
    assert owner is not None
    reference = DictionaryObject({
        NameObject("/Type"): NameObject("/OBJR"),
        NameObject("/Obj"): annotation,
        NameObject("/Pg"): owner,
    })
    target = cast("DictionaryObject", element.get_object())
    kids = target.get("/K")
    items = list(kids) if isinstance(kids, ArrayObject) else []
    target[NameObject("/K")] = ArrayObject([*items, reference])


def annotation_references(writer: PdfWriter) -> list[IndirectObject]:
    """List the first page's annotations.

    Returns
    -------
    list[IndirectObject]
        References to the page's annotation dictionaries.

    """
    annotations = writer.pages[0]["/Annots"]
    assert isinstance(annotations, ArrayObject)
    return list(annotations)


def _link_annotation(uri: str, x: float, y: float) -> DictionaryObject:
    return DictionaryObject({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Link"),
        NameObject("/Rect"): ArrayObject([FloatObject(v) for v in (x, y, x + 40, y + 10)]),
        NameObject("/A"): DictionaryObject({
            NameObject("/S"): NameObject("/URI"),
            NameObject("/URI"): TextStringObject(uri),
        }),
    })


def text_pdf(
    path: Path,
    pages: Sequence[Sequence[str]],
    *,
    size: tuple[float, float] = (200, 200),
    top: float = 180,
    links: Sequence[str] = (),
) -> Path:
    """Write a PDF whose pages hold the given lines of text; ``links`` land on page one.

    Returns
    -------
    Path
        The written file.

    """
    writer = PdfWriter()
    for index, lines in enumerate(pages):
        page = writer.add_blank_page(width=size[0], height=size[1])
        _write_text(writer, page, lines, top)
        if index == 0 and links:
            annotations: list[Any] = [
                writer._add_object(_link_annotation(uri, 10, 20 + 15 * n))
                for n, uri in enumerate(links)
            ]
            page[NameObject("/Annots")] = ArrayObject(annotations)
    writer.write(path)
    return path
