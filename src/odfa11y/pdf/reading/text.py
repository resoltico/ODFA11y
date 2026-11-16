# SPDX-License-Identifier: MPL-2.0
"""Give pypdf text extraction predecoded content and budget-owned auxiliary streams."""

from collections.abc import Callable

from pypdf import PageObject
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    StreamObject,
)

from odfa11y.errors import ToolFailure
from odfa11y.pdf.reading.objects import dictionary, resolve
lazy from odfa11y.pdf.reading.reader import _Invocation


class _AuxiliaryStream(DecodedStreamObject):
    def __init__(self, source: StreamObject, data: Callable[[StreamObject], bytes]) -> None:
        super().__init__()
        self.update({
            key: value
            for key, value in source.items()
            if key not in {"/Filter", "/DecodeParms", "/Length"}
        })
        self._source = source
        self._read = data

    def get_data(self) -> bytes:
        return self._read(self._source)


def text_page(
    page: PageObject, invocation: _Invocation, data: Callable[[StreamObject], bytes]
) -> PageObject:
    view = PageObject(page.pdf)
    view.update(page)
    content = DecodedStreamObject()
    content.set_data(invocation.data)
    view[NameObject("/Contents")] = content
    view[NameObject("/Resources")] = _resources(invocation, data)
    return view


def _resources(invocation: _Invocation, data: Callable[[StreamObject], bytes]) -> DictionaryObject:
    resources = DictionaryObject(invocation.resources)
    resources[NameObject("/Font")] = DictionaryObject({
        name: _font(dictionary(value), data, frozenset())
        for name, value in dictionary(resources.get("/Font")).items()
    })
    objects = DictionaryObject()
    for name, reference in dictionary(resources.get("/XObject")).items():
        value = resolve(reference)
        if name in invocation.forms:
            child = invocation.forms[name]
            form = DecodedStreamObject()
            form.update({
                key: val
                for key, val in dictionary(value).items()
                if key not in {"/Filter", "/DecodeParms", "/Length"}
            })
            form.set_data(child.data)
            form[NameObject("/Resources")] = _resources(child, data)
            objects[name] = form
        elif isinstance(value, DictionaryObject) and value.get("/Subtype") == "/Image":
            objects[name] = DictionaryObject({NameObject("/Subtype"): NameObject("/Image")})
    resources[NameObject("/XObject")] = objects
    return resources


def _font(
    font: DictionaryObject, data: Callable[[StreamObject], bytes], active: frozenset[int]
) -> DictionaryObject:
    if id(font) in active:
        message = "Cyclic PDF descendant fonts prevent complete text inspection"
        raise ToolFailure(message)
    view = DictionaryObject(font)
    for key in ("/ToUnicode", "/Encoding"):
        stream = resolve(font.get(key))
        if isinstance(stream, StreamObject):
            view[NameObject(key)] = _AuxiliaryStream(stream, data)
    descriptor = dictionary(font.get("/FontDescriptor"))
    if descriptor:
        descriptor = DictionaryObject(descriptor)
        for key in ("/FontFile", "/FontFile2", "/FontFile3"):
            stream = resolve(descriptor.get(key))
            if isinstance(stream, StreamObject):
                descriptor[NameObject(key)] = _AuxiliaryStream(stream, data)
        view[NameObject("/FontDescriptor")] = descriptor
    descendants = resolve(font.get("/DescendantFonts"))
    if isinstance(descendants, ArrayObject):
        view[NameObject("/DescendantFonts")] = ArrayObject([
            _font(dictionary(child), data, active | {id(font)}) for child in descendants
        ])
    return view
