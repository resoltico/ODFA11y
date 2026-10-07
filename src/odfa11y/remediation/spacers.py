# SPDX-License-Identifier: MPL-2.0
"""Remove empty body paragraphs that only create visual space."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from odfa11y.odf import qn, spacer_candidates

from .outcome import Operation, Outcome, Status

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdtDocument, StyleCatalog


@dataclass(frozen=True, slots=True)
class RemoveEmptySpacers(Operation):
    """Remove empty body paragraphs that carry no content, structure or break semantics."""

    name: ClassVar[str] = "remove_empty_spacers"

    @override
    def apply(self, document: OdtDocument) -> tuple[Outcome, ...]:
        count = remove_empty_spacer_paragraphs(document.tree("content.xml"), document.catalog)
        if not count:
            return (Outcome(self.name, Status.UNCHANGED, "No removable spacer paragraphs."),)
        document.edit("content.xml")
        message = f"Removed {count} empty spacer paragraph(s) without break semantics."
        return (Outcome(self.name, Status.APPLIED, message, count=count),)


def remove_empty_spacer_paragraphs(tree: etree._ElementTree, catalog: StyleCatalog) -> int:
    """Remove empty body spacers while preserving structural and break semantics.

    Returns
    -------
    int
        The number of removed body paragraphs.

    """
    removed = 0
    for paragraph in spacer_candidates(tree):
        if catalog.has_break_semantics(paragraph.get(qn("text", "style-name"))):
            continue
        parent = paragraph.getparent()
        if parent is None:
            continue
        parent.remove(paragraph)
        removed += 1
    return removed
