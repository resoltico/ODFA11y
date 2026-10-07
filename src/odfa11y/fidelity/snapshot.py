# SPDX-License-Identifier: MPL-2.0
"""Read what a comparison needs from a PDF: page sizes, text and link targets."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from odfa11y.errors import ToolFailedError

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
        with Path(path).open("rb") as stream:
            return _snapshot(PdfReader(stream, strict=True))
    except (OSError, PyPdfError, ValueError, KeyError) as exc:
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
    for item in annotations.get_object():
        annotation = item.get_object()
        if annotation.get("/Subtype") != "/Link":
            continue
        action = annotation.get("/A")
        uri = action.get_object().get("/URI") if action is not None else None
        if isinstance(uri, str):
            targets.append(uri)
    return targets
