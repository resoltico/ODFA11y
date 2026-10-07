# SPDX-License-Identifier: MPL-2.0
"""List the fonts a PDF uses and whether each is embedded."""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from odfa11y.errors import ToolFailedError
from odfa11y.pdf_limits import MAX_PDF_PAGES, check_file_size

from .structure_walk import pdf_dictionary

SUBSET_TAG = re.compile(r"^[A-Z]{6}\+")
FONT_FILE_KEYS = ("/FontFile", "/FontFile2", "/FontFile3")


def list_fonts(path: str | Path) -> list[dict[str, object]]:
    """Name the fonts used on the pages of a PDF.

    Returns
    -------
    list[dict[str, object]]
        One entry per distinct font name (subset tags removed) with its embedded flag,
        sorted by name; empty when the file cannot be read.

    """
    try:
        fonts = _collect(Path(path))
    except OSError, PyPdfError, ValueError, KeyError, TypeError, AttributeError, ToolFailedError:
        return []
    return [{"name": name, "embedded": fonts[name]} for name in sorted(fonts)]


def _collect(path: Path) -> dict[str, bool]:
    check_file_size(path)
    fonts: dict[str, bool] = {}
    with path.open("rb") as stream:
        reader = PdfReader(stream, strict=False)
        for page in list(reader.pages)[:MAX_PDF_PAGES]:
            resources = pdf_dictionary(page.get("/Resources"))
            for font in pdf_dictionary(resources.get("/Font")).values():
                name, embedded = _describe(pdf_dictionary(font))
                if name:
                    fonts[name] = fonts.get(name, False) or embedded
    return fonts


def _describe(font: object) -> tuple[str, bool]:
    base = pdf_dictionary(font)
    name = SUBSET_TAG.sub("", str(base.get("/BaseFont", "")).removeprefix("/"))
    descriptor_sources = [base]
    descendants = base.get("/DescendantFonts")
    if descendants is not None:
        descendants = descendants.get_object()
        descriptor_sources += [pdf_dictionary(item) for item in descendants]
    embedded = any(
        key in pdf_dictionary(source.get("/FontDescriptor"))
        for source in descriptor_sources
        for key in FONT_FILE_KEYS
    )
    return name, embedded
