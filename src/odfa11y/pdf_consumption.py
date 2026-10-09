# SPDX-License-Identifier: MPL-2.0
"""Bound decoded streams and invocation work before PDF inspection or extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.util import find_spec
from typing import TYPE_CHECKING

from pypdf import apply_configuration
from pypdf.errors import PdfReadError
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, StreamObject

from odfa11y.errors import ToolFailedError
from odfa11y.pdf_content import scan_content
from odfa11y.pdf_limits import MAX_CONTENT_BYTES

if TYPE_CHECKING:
    from pypdf import PdfReader

MAX_CONTENT_STREAMS = 10_000
MAX_FORM_DEPTH = 50
MAX_FORM_INVOCATIONS = 5_000


def resolve(value: object) -> object:
    """Resolve an indirect value.

    Returns
    -------
    object
        The direct PDF value.

    """
    return value.get_object() if isinstance(value, IndirectObject) else value


def dictionary(value: object) -> DictionaryObject:
    """Resolve an optional dictionary and reject other present shapes.

    Returns
    -------
    DictionaryObject
        The dictionary or an empty one for absent values.

    Raises
    ------
    PdfReadError
        A present value is not a dictionary.

    """
    value = resolve(value)
    if value is None:
        return DictionaryObject()
    if not isinstance(value, DictionaryObject):
        msg = "Expected a PDF dictionary"
        raise PdfReadError(msg)
    return value


@dataclass(slots=True)
class _Budget:
    reader: PdfReader
    limit: int
    decoded: int = 0
    work: int = 0
    invocations: int = 0
    seen: set[int] = field(default_factory=set)
    auxiliary_resources: dict[int, DictionaryObject] = field(default_factory=dict)

    def data(self, stream: StreamObject) -> bytes:
        remaining = self.limit - self.decoded
        with apply_configuration(
            zlib_maximum_output_length=max(remaining + 1, 1),
            lzw_maximum_output_length=max(remaining + 1, 1),
            run_length_maximum_output_length=max(remaining + 1, 1),
            array_based_stream_maximum_output_length=max(remaining + 1, 1),
        ):
            try:
                data = stream.get_data()
            except NotImplementedError as exc:
                msg = f"Unsupported PDF stream decoding: {str(exc)[:200]}"
                raise ToolFailedError(msg) from exc
        if id(stream) not in self.seen:
            self.seen.add(id(stream))
            self.decoded += len(data)
        if self.decoded > self.limit:
            self.refuse("Decoded PDF streams")
        return data

    def refuse(self, reason: str) -> None:
        msg = f"{reason} exceed the {self.limit}-byte inspection limit"
        raise ToolFailedError(msg)

    def auxiliary(self, resources: DictionaryObject) -> None:
        if id(resources) in self.auxiliary_resources:
            return
        # Inspect only auxiliary streams used by pypdf text extraction.
        for value in dictionary(resources.get("/Font")).values():
            font = dictionary(value)
            _font_shapes(font)
            for key in ("/ToUnicode", "/Encoding"):
                stream = resolve(font.get(key))
                if isinstance(stream, StreamObject):
                    self.data(stream)
            self.font_program(font)
        # Retain identities so absent-resource dictionaries cannot be confused after reuse.
        self.auxiliary_resources[id(resources)] = resources

    def font_program(self, font: DictionaryObject) -> None:
        if font.get("/Subtype") != "/Type1" or "/ToUnicode" in font:
            return
        descriptor = dictionary(font.get("/FontDescriptor"))
        stream = resolve(descriptor.get("/FontFile"))
        if isinstance(stream, StreamObject):
            self.data(stream)
            return
        stream = resolve(descriptor.get("/FontFile3"))
        if (
            isinstance(stream, StreamObject)
            and stream.get("/Subtype") == "/Type1C"
            and find_spec("fontTools") is not None
        ):
            self.data(stream)

    def content(
        self, contents: object, resources: DictionaryObject, active: frozenset[int]
    ) -> None:
        streams = resolve(contents)
        items = streams if isinstance(streams, ArrayObject) else [streams]
        parts: list[bytes] = []
        if len(items) > MAX_CONTENT_STREAMS:
            msg = "PDF content array exceeds the stream-count limit"
            raise ToolFailedError(msg)
        for item in items:
            stream = resolve(item)
            if stream is None:
                continue
            if not isinstance(stream, StreamObject):
                msg = "Expected a PDF content stream"
                raise PdfReadError(msg)
            data = self.data(stream)
            parts.append(data)
            self.work += len(data)
            if self.work > self.limit:
                self.refuse("PDF invocation work")
        self.work += max(len(parts) - 1, 0)
        if self.work > self.limit:
            self.refuse("PDF invocation work")
        self.auxiliary(resources)
        objects = dictionary(resources.get("/XObject"))
        if not objects:
            return

        def invoke(name: str, _context: tuple[bool, bool]) -> bool:
            form = resolve(objects.get(name))
            if isinstance(form, StreamObject) and form.get("/Subtype") == "/Form":
                self.form(form, resources, active)
            return False

        scan_content(b"\n".join(parts), lambda _: None, invoke=invoke)

    def form(self, form: StreamObject, inherited: DictionaryObject, active: frozenset[int]) -> None:
        if "/StructParent" in form:
            msg = "Whole-object Form ownership prevents complete content inspection"
            raise ToolFailedError(msg)
        self.invocations += 1
        if (
            id(form) in active
            or len(active) >= MAX_FORM_DEPTH
            or self.invocations > MAX_FORM_INVOCATIONS
        ):
            msg = "PDF Form cycle, depth or invocation limit prevents complete inspection"
            raise ToolFailedError(msg)
        resources = dictionary(form.get("/Resources")) if "/Resources" in form else inherited
        self.content(form, resources, active | {id(form)})


def check_consumption(reader: PdfReader, limit: int | None = None) -> None:
    """Preflight consumed page/Form content and auxiliary text/XMP streams.

    Unique stream objects count once toward decoded bytes; every page/Form invocation counts
    toward content work. Filter intermediates use pypdf's scoped decoding controls. Parser
    allocations and filters without incremental controls still require external OS isolation.

    Decoded bytes, invocation work, Form depth or cycles prevent complete inspection with
    ``ToolFailedError``.

    """
    budget = _Budget(reader, MAX_CONTENT_BYTES if limit is None else limit)
    metadata = resolve(reader.root_object.get("/Metadata"))
    if isinstance(metadata, StreamObject):
        budget.data(metadata)
    for page in reader.pages:
        budget.content(page.get("/Contents"), dictionary(page.get("/Resources")), frozenset())


def _font_shapes(font: DictionaryObject) -> None:
    for key in ("/Subtype", "/BaseFont"):
        value = resolve(font.get(key))
        if value is not None and not isinstance(value, str):
            msg = f"Expected a PDF font name for {key}"
            raise PdfReadError(msg)
    dictionary(font.get("/FontDescriptor"))
    for key in ("/DescendantFonts", "/Widths"):
        value = resolve(font.get(key))
        if value is not None and not isinstance(value, ArrayObject):
            msg = f"Expected a PDF font array for {key}"
            raise PdfReadError(msg)
    descendants = resolve(font.get("/DescendantFonts"))
    if isinstance(descendants, ArrayObject):
        for child in descendants:
            dictionary(dictionary(child).get("/FontDescriptor"))
