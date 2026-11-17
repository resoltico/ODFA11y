# SPDX-License-Identifier: AGPL-3.0-only
"""Own every decoded stream and one bounded walk of invoked page and Form content."""

import os
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from importlib.util import find_spec
from pathlib import Path
from typing import BinaryIO

from pypdf import PageObject, PdfReader, apply_configuration
from pypdf.errors import PdfReadError, PyPdfError
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    NumberObject,
    StreamObject,
)

from odfa11y.errors import ToolFailure
from odfa11y.pdf.reading.content import ContentScan, scan_content
from odfa11y.pdf.reading.limits import Limits, default_limits
from odfa11y.pdf.reading.objects import dictionary, resolve, xref
from odfa11y.pdf.reading.structure import build_tree
lazy from odfa11y.pdf.reading.text import text_page


@dataclass(frozen=True, slots=True)
class PageContent:
    page: PageObject
    scopes: tuple[tuple[int | None, ContentScan], ...]


@dataclass(slots=True)
class _Invocation:
    data: bytes
    resources: DictionaryObject
    scan: ContentScan
    stream: StreamObject | None = None
    forms: dict[str, _Invocation] = field(default_factory=dict)


@dataclass(slots=True)
class _Consumption:
    limits: Limits
    decoded: int = 0
    work: int = 0
    invocations: int = 0
    streams: dict[int, tuple[StreamObject, bytes]] = field(default_factory=dict)
    resources: dict[int, DictionaryObject] = field(default_factory=dict)
    failure: Exception | None = None

    def data(self, stream: StreamObject) -> bytes:
        if (known := self.streams.get(id(stream))) is not None:
            return known[1]
        remaining = self.limits.decoded_bytes - self.decoded
        try:
            with _decoding_configuration(remaining):
                data = stream.get_data()
            self.decoded += len(data)
            if self.decoded > self.limits.decoded_bytes:
                self.refuse("Decoded PDF streams", self.limits.decoded_bytes)
        except TypeError as error:
            self.failure = PdfReadError(
                f"Malformed PDF stream decoding parameters: {str(error)[:200]}"
            )
            raise self.failure from error
        except NotImplementedError as error:
            self.failure = ToolFailure(f"Unsupported PDF stream decoding: {str(error)[:200]}")
            raise self.failure from error
        except (PyPdfError, ToolFailure, ValueError, RecursionError) as error:
            self.failure = error
            raise
        self.streams[id(stream)] = stream, data
        return data

    def refuse(self, reason: str, limit: int) -> None:
        self.failure = ToolFailure(f"{reason} exceed the {limit}-byte inspection limit")
        raise self.failure

    def auxiliary(self, resources: DictionaryObject) -> None:
        if id(resources) in self.resources:
            return
        self.resources[id(resources)] = resources
        for value in dictionary(resources.get("/Font")).values():
            font = dictionary(value)
            _font_shapes(font)
            for key in ("/ToUnicode", "/Encoding"):
                stream = resolve(font.get(key))
                if isinstance(stream, StreamObject):
                    self.data(stream)
            if font.get("/Subtype") in {"/Type1", "/MMType1"} and "/ToUnicode" not in font:
                self._font_program(font)

    def _font_program(self, font: DictionaryObject) -> None:
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

    def content(self, contents: object) -> bytes:
        value = resolve(contents)
        items = value if isinstance(value, ArrayObject) else [value]
        if len(items) > self.limits.content_streams:
            message = "PDF content array exceeds the stream-count limit"
            raise ToolFailure(message)
        parts = []
        for item in items:
            stream = resolve(item)
            if stream is None:
                continue
            if not isinstance(stream, StreamObject):
                message = "Expected a PDF content stream"
                raise PdfReadError(message)
            data = self.data(stream)
            self.work += len(data) + bool(parts)
            if self.work > self.limits.invocation_bytes:
                self.refuse("PDF invocation work", self.limits.invocation_bytes)
            parts.append(data)
        return b"\n".join(parts)

    def walk(
        self,
        contents: object,
        resources: DictionaryObject,
        scopes: dict[int | None, ContentScan],
        *,
        stream: StreamObject | None = None,
        active: frozenset[int] = frozenset(),
        context: tuple[bool, bool] = (False, False),
    ) -> _Invocation:
        self.auxiliary(resources)
        data = self.content(contents)
        forms: dict[str, _Invocation] = {}
        properties = dictionary(resources.get("/Properties"))
        objects = dictionary(resources.get("/XObject"))

        def property_mcid(name: str) -> int | None:
            value = dictionary(properties.get(name)).get("/MCID")
            return int(value) if isinstance(value, NumberObject) else None

        def invoke(name: str, inherited: tuple[bool, bool]) -> bool:
            form = resolve(objects.get(name))
            if not isinstance(form, StreamObject) or form.get("/Subtype") != "/Form":
                return False
            self._enter_form(form, active)
            own = dictionary(form.get("/Resources")) if "/Resources" in form else resources
            child = self.walk(
                form, own, scopes, stream=form, active=active | {id(form)}, context=inherited
            )
            forms[name] = child
            return child.scan.graphical_content

        scan = scan_content(
            data, property_mcid, _image_presence(objects), invoke=invoke, context=context
        )
        _accumulate(
            scopes.setdefault(xref(stream) if stream is not None else None, ContentScan()), scan
        )
        return _Invocation(data, resources, scan, stream, forms)

    def _enter_form(self, form: StreamObject, active: frozenset[int]) -> None:
        if "/StructParent" in form:
            message = "Whole-object Form ownership prevents complete content inspection"
            raise ToolFailure(message)
        self.invocations += 1
        if (
            id(form) in active
            or len(active) >= self.limits.form_depth
            or self.invocations > self.limits.form_invocations
        ):
            message = "PDF Form cycle, depth or invocation limit prevents complete inspection"
            raise ToolFailure(message)
        if xref(form) is None:
            message = "Cannot inspect a Form without an indirect stream identity"
            raise ToolFailure(message)


class BoundedPdf:
    """One open PDF and its bounded stream, structure, resource and invocation observations."""

    def __init__(self, path: Path, stream: BinaryIO, limits: Limits) -> None:
        if os.fstat(stream.fileno()).st_size > limits.stored_bytes:
            message = f"PDF {path.name} exceeds the {limits.stored_bytes}-byte limit"
            raise ToolFailure(message)
        self.limits = limits
        self._consumption = _Consumption(limits)
        self._reader = PdfReader(stream, strict=True)
        count = len(self._reader.pages)
        if count > limits.pages:
            message = f"PDF {path.name} has {count} pages; the limit is {limits.pages}"
            raise ToolFailure(message)
        self.pages = tuple(self._reader.pages)
        self.catalog = dictionary(self._reader.root_object)
        self.structure = build_tree(
            dictionary(self.catalog.get("/StructTreeRoot")), limits.structure_nodes
        )
        self.metadata = self._reader.metadata
        self.header = self._reader.pdf_header
        metadata = resolve(self.catalog.get("/Metadata"))
        if isinstance(metadata, StreamObject):
            self.data(metadata)
        self._invocations = []
        contents = []
        for page in self.pages:
            scopes = {}
            invocation = self._consumption.walk(
                page.get("/Contents"), dictionary(page.get("/Resources")), scopes
            )
            self._invocations.append(invocation)
            contents.append(PageContent(page, tuple(scopes.items())))
        self.contents = tuple(contents)

    def data(self, stream: StreamObject) -> bytes:
        return self._consumption.data(stream)

    @property
    def resources(self) -> tuple[DictionaryObject, ...]:
        return tuple(self._consumption.resources.values())

    def text(self, index: int) -> str:
        try:
            text = (
                text_page(self.pages[index], self._invocations[index], self.data).extract_text()
                or ""
            )
        except (PyPdfError, ValueError, TypeError, RecursionError) as error:
            message = f"Cannot extract bounded PDF text: {error}"
            raise ToolFailure(message) from error
        # pypdf catches some Form/font errors internally; a budget refusal cannot be swallowed.
        if self._consumption.failure is not None:
            raise self._consumption.failure
        return text


@contextmanager
def open_pdf(path: str | Path, limits: Limits | None = None) -> Generator[BoundedPdf]:
    path = Path(path)
    selected = limits if limits is not None else default_limits()
    # Keep parser filter controls active for lazy object reads too. Parser allocations
    # still require OS isolation; content and auxiliary decoding also use the ledger.
    with path.open("rb") as stream, _decoding_configuration(selected.decoded_bytes):
        yield BoundedPdf(path, stream, selected)


def _decoding_configuration(remaining: int):
    maximum = max(remaining + 1, 1)
    return apply_configuration(
        zlib_maximum_output_length=maximum,
        lzw_maximum_output_length=maximum,
        run_length_maximum_output_length=maximum,
        array_based_stream_maximum_output_length=maximum,
    )


def _accumulate(target: ContentScan, source: ContentScan) -> None:
    target.mcids.update(source.mcids)
    target.graphical_mcids.update(source.graphical_mcids)
    target.unmarked_text_operations += source.unmarked_text_operations
    target.graphical_content |= source.graphical_content
    target.image_operations += source.image_operations
    target.artifact_image_operations += source.artifact_image_operations


def _image_presence(objects: DictionaryObject) -> Callable[[str], bool]:
    def is_image(name: str) -> bool:
        image = resolve(objects.get(name))
        if not isinstance(image, StreamObject) or image.get("/Subtype") != "/Image":
            return False
        width, height = image.get("/Width"), image.get("/Height")
        return (
            isinstance(width, NumberObject)
            and width > 0
            and isinstance(height, NumberObject)
            and height > 0
            # Inspect stored bytes only; image decompression is outside this structural claim.
            and bool(StreamObject.get_data(image))
        )

    return is_image


def _font_shapes(font: DictionaryObject) -> None:
    for key in ("/Subtype", "/BaseFont"):
        value = resolve(font.get(key))
        if value is not None and not isinstance(value, str):
            message = f"Expected a PDF font name for {key}"
            raise PdfReadError(message)
    dictionary(font.get("/FontDescriptor"))
    for key in ("/DescendantFonts", "/Widths"):
        value = resolve(font.get(key))
        if value is not None and not isinstance(value, ArrayObject):
            message = f"Expected a PDF font array for {key}"
            raise PdfReadError(message)
    descendants = resolve(font.get("/DescendantFonts"))
    if isinstance(descendants, ArrayObject):
        for child in descendants:
            dictionary(dictionary(child).get("/FontDescriptor"))
