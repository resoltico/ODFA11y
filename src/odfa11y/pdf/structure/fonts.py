# SPDX-License-Identifier: AGPL-3.0-only
"""Name fonts in the bounded reader's inspected page and Form resource scopes."""

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf.errors import PdfReadError, PyPdfError
from pypdf.generic import ArrayObject

from odfa11y.errors import ToolFailure
from odfa11y.pdf.reading import BoundedPdf, open_pdf
from odfa11y.pdf.reading.objects import dictionary, resolve

SUBSET_TAG = re.compile(r"^[A-Z]{6}\+")
FONT_FILE_KEYS = ("/FontFile", "/FontFile2", "/FontFile3")


@dataclass(frozen=True, slots=True)
class Font:
    name: str
    embedded: bool


def list_fonts(path: str | Path) -> tuple[Font, ...]:
    try:
        with open_pdf(path) as pdf:
            return read_fonts(pdf)
    except (OSError, PyPdfError, ValueError, KeyError, RecursionError) as error:
        message = f"Cannot inspect PDF fonts: {error}"
        raise ToolFailure(message) from error


def read_fonts(pdf: BoundedPdf) -> tuple[Font, ...]:
    found: dict[str, bool] = {}
    for resources in pdf.resources:
        for value in dictionary(resources.get("/Font")).values():
            name, embedded = _describe(value)
            if name:
                found[name] = found.get(name, False) or embedded
    return tuple(Font(name, found[name]) for name in sorted(found))


def _describe(font: object) -> tuple[str, bool]:
    base = dictionary(font)
    name = SUBSET_TAG.sub("", str(base.get("/BaseFont", "")).removeprefix("/"))
    descriptor_sources = [base]
    descendants = resolve(base.get("/DescendantFonts"))
    if descendants is not None:
        if not isinstance(descendants, ArrayObject):
            message = "Expected a PDF descendant-font array"
            raise PdfReadError(message)
        descriptor_sources += [dictionary(item) for item in descendants]
    embedded = any(
        key in dictionary(source.get("/FontDescriptor"))
        for source in descriptor_sources
        for key in FONT_FILE_KEYS
    )
    return name, embedded
