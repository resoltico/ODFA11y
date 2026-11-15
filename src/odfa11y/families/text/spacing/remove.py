# SPDX-License-Identifier: MPL-2.0
"""Remove empty body paragraphs that only create visual space."""

from dataclasses import dataclass
from typing import ClassVar, override

lazy from lxml import etree

from odfa11y.concepts.edits import Operation, Outcome, Status
from odfa11y.errors import RemediationError
from odfa11y.families.text.spacing.candidates import spacer_candidates
from odfa11y.families.text.styles.catalogue import catalog_of
from odfa11y.odf import Family, Part
from odfa11y.odf import names as xml_names
lazy from odfa11y.families.text.styles.catalogue import StyleCatalog
lazy from odfa11y.odf import OdfDocument


@dataclass(frozen=True, slots=True)
class RemoveEmptySpacers(Operation):
    """Remove empty body paragraphs that carry no content, structure or break semantics."""

    name: ClassVar[str] = "remove_empty_spacers"
    families: ClassVar[frozenset[Family] | None] = frozenset({Family.TEXT})

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        try:
            count = remove_empty_spacer_paragraphs(
                document.tree(Part.CONTENT), catalog_of(document)
            )
        except RemediationError as exc:
            return (Outcome(self.name, Status.FAILED, str(exc)),)
        if not count:
            return (Outcome(self.name, Status.UNCHANGED, "No removable spacer paragraphs."),)
        message = f"Removed {count} empty spacer paragraph(s) without break semantics."
        return (Outcome(self.name, Status.APPLIED, message, count=count),)


def remove_empty_spacer_paragraphs(tree: etree._ElementTree, catalog: StyleCatalog) -> int:
    """Remove empty body spacers while preserving structural and break semantics.

    Returns
    -------
    int
        The number of removed body paragraphs.

    """
    candidates = [
        paragraph
        for paragraph in spacer_candidates(tree)
        if not catalog.has_break_semantics(paragraph.get(xml_names.TEXT_STYLE_NAME))
    ]
    removed = 0
    for paragraph in candidates:
        parent = paragraph.getparent()
        if parent is None:
            continue
        parent.remove(paragraph)
        removed += 1
    return removed
