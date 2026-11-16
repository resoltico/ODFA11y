# SPDX-License-Identifier: AGPL-3.0-only
"""Resolve PDF objects and their typed scalar identities in one place."""

from collections.abc import Iterator

from pypdf.errors import PdfReadError
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, NameObject, NullObject


def resolve(value: object) -> object:
    return value.get_object() if isinstance(value, IndirectObject) else value


def dictionary(value: object) -> DictionaryObject:
    value = resolve(value)
    if value is None:
        return DictionaryObject()
    if not isinstance(value, DictionaryObject):
        message = "Expected a PDF dictionary"
        raise PdfReadError(message)
    return value


def xref(value: object) -> int | None:
    if isinstance(value, IndirectObject):
        return value.idnum
    reference = getattr(value, "indirect_reference", None)
    return reference.idnum if isinstance(reference, IndirectObject) else None


def has_text(value: object) -> bool:
    value = resolve(value)
    return isinstance(value, str) and bool(value.strip())


def text(value: object) -> str | None:
    value = resolve(value)
    return value if isinstance(value, str) else None


def annotation_objects(page: DictionaryObject) -> Iterator[tuple[object, DictionaryObject]]:
    """Validate annotation shapes, retaining original references for correspondence checks."""
    values = resolve(page.get("/Annots"))
    # PDF32000-1 7.3.7: null dictionary values have the meaning of absent entries.
    if values is None or isinstance(values, NullObject):
        return
    if not isinstance(values, ArrayObject):
        message = "Expected a PDF annotation array"
        raise PdfReadError(message)
    for item in values:
        annotation = resolve(item)
        if not isinstance(annotation, DictionaryObject):
            message = "Expected a PDF annotation dictionary"
            raise PdfReadError(message)
        if not isinstance(resolve(annotation.get("/Subtype")), NameObject):
            message = "Expected a PDF annotation subtype name"
            raise PdfReadError(message)
        yield item, annotation
