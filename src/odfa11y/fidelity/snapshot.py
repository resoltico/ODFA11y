# SPDX-License-Identifier: MPL-2.0
"""Read what a comparison needs from a PDF: page sizes, text and link targets."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pypdf import PdfReader
from pypdf.errors import PdfReadError, PyPdfError
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

from odfa11y.errors import ToolFailedError
from odfa11y.pdf_consumption import check_consumption
from odfa11y.pdf_limits import check_file_size, check_limits

if TYPE_CHECKING:
    from pypdf import PageObject

SIZE_PRECISION = 1


@dataclass(frozen=True, slots=True)
class PageSnapshot:
    """A page's size in points and its normalized text."""

    width: float
    height: float
    text: str


@dataclass(frozen=True, slots=True)
class PdfSnapshot:
    """Pages plus the multiset of external link targets."""

    pages: tuple[PageSnapshot, ...]
    links: Counter[str]

    @property
    def text(self) -> str:
        """All page text in document order, whitespace-normalized."""
        return " ".join(page.text for page in self.pages if page.text)


def read_snapshot(path: str | Path) -> PdfSnapshot:
    """Extract page geometry, text and link URIs from a PDF.

    Returns
    -------
    PdfSnapshot
        The comparison inputs.

    Raises
    ------
    ToolFailedError
        The file cannot be read as a PDF.

    """
    try:
        check_file_size(path)
        with Path(path).open("rb") as stream:
            reader = PdfReader(stream, strict=True)
            check_limits(path, len(reader.pages))
            check_consumption(reader)
            return _snapshot(reader)
    except (OSError, PyPdfError, ValueError, KeyError, RecursionError) as exc:
        msg = f"Cannot read PDF {path}: {exc}"
        raise ToolFailedError(msg) from exc


def _snapshot(reader: PdfReader) -> PdfSnapshot:
    pages = []
    links: Counter[str] = Counter()
    for page in reader.pages:
        box = page.mediabox
        text = " ".join((page.extract_text() or "").split())
        pages.append(
            PageSnapshot(
                round(float(box.width), SIZE_PRECISION),
                round(float(box.height), SIZE_PRECISION),
                text,
            )
        )
        links.update(_link_targets(page))
    return PdfSnapshot(tuple(pages), links)


def _link_targets(page: PageObject) -> list[str]:
    annotations = page.get("/Annots")
    if annotations is None:
        return []
    targets = []
    annotations = _resolve(annotations)
    if not isinstance(annotations, ArrayObject):
        msg = "Expected a PDF annotation array"
        raise PdfReadError(msg)
    for item in annotations:
        annotation = _resolve(item)
        if not isinstance(annotation, DictionaryObject):
            msg = "Expected a PDF annotation dictionary"
            raise PdfReadError(msg)
        if annotation.get("/Subtype") != "/Link":
            continue
        action = _resolve(annotation.get("/A"))
        if action is not None and not isinstance(action, DictionaryObject):
            msg = "Expected a PDF action dictionary"
            raise PdfReadError(msg)
        uri = _resolve(action.get("/URI")) if action is not None else None
        if uri is not None and not isinstance(uri, str):
            msg = "Expected a PDF URI string"
            raise PdfReadError(msg)
        if isinstance(uri, str):
            targets.append(uri)
    return targets


def _resolve(value: object) -> object:
    return value.get_object() if isinstance(value, IndirectObject) else value
