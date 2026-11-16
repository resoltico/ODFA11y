# SPDX-License-Identifier: MPL-2.0
"""Resolve PDF objects and their typed scalar identities in one place."""

from pypdf.errors import PdfReadError
from pypdf.generic import DictionaryObject, IndirectObject


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
