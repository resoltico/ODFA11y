# SPDX-License-Identifier: MPL-2.0
"""Read what a comparison needs from a PDF: page sizes, text and link targets."""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pypdf.errors import PdfReadError, PyPdfError
from pypdf.generic import DictionaryObject, NameObject
lazy from pypdf import PageObject

from odfa11y.errors import ToolFailure
from odfa11y.pdf.fidelity.uri import effective_uri, uri_base
from odfa11y.pdf.reading import BoundedPdf, open_pdf
from odfa11y.pdf.reading.objects import annotation_objects, resolve

SIZE_PRECISION = 1


@dataclass(frozen=True, slots=True)
class PageSnapshot:
    """A page's size in points and its normalized text."""

    width: float
    height: float
    text: str


@dataclass(frozen=True, slots=True)
class UriIssue:
    page: int | None
    problem: str


@dataclass(frozen=True, slots=True)
class PdfSnapshot:
    """Pages plus the multiset of external link targets."""

    pages: tuple[PageSnapshot, ...]
    links: tuple[tuple[str, int], ...]
    issues: tuple[UriIssue, ...] = ()

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
    ToolFailure
        The file cannot be read as a PDF.

    """
    try:
        with open_pdf(path) as reader:
            return _snapshot(reader)
    except (OSError, PyPdfError, ValueError, KeyError, RecursionError) as exc:
        msg = f"Cannot read PDF {path}: {exc}"
        raise ToolFailure(msg) from exc


def _snapshot(reader: BoundedPdf) -> PdfSnapshot:
    pages = []
    links: Counter[str] = Counter()
    issues = []
    try:
        base = uri_base(reader.catalog)
    except PdfReadError as error:
        base = None
        issues.append(UriIssue(None, str(error)))
    for index, page in enumerate(reader.pages):
        box = page.mediabox
        text = " ".join((reader.text(index)).split())
        pages.append(
            PageSnapshot(
                round(float(box.width), SIZE_PRECISION),
                round(float(box.height), SIZE_PRECISION),
                text,
            )
        )
        links.update(_link_targets(page, base, index + 1, issues))
    return PdfSnapshot(tuple(pages), tuple(sorted(links.items())), tuple(issues))


def _link_targets(
    page: PageObject, base: str | None, number: int, issues: list[UriIssue]
) -> list[str]:
    targets = []
    for _item, annotation in annotation_objects(page):
        if resolve(annotation.get("/Subtype")) != "/Link":
            continue
        try:
            target = _action_uri(annotation, base)
        except PdfReadError as error:
            issues.append(UriIssue(number, str(error)))
        else:
            if target is not None:
                targets.append(target)
    return targets


def _action_uri(annotation: DictionaryObject, base: str | None) -> str | None:
    action = resolve(annotation.get("/A"))
    if action is None:
        return None
    if not isinstance(action, DictionaryObject):
        message = "Expected a PDF action dictionary"
        raise PdfReadError(message)
    subtype = resolve(action.get("/S"))
    if not isinstance(subtype, NameObject):
        message = "Expected a PDF action subtype"
        raise PdfReadError(message)
    return effective_uri(resolve(action.get("/URI")), base) if subtype == "/URI" else None
