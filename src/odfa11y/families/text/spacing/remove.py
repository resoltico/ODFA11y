# SPDX-License-Identifier: AGPL-3.0-only
"""Remove empty body paragraphs that only create visual space."""

lazy from lxml import etree

from odfa11y.decisions import Decision
from odfa11y.decisions.answers import SwitchAnswer
from odfa11y.decisions.edit import EditResult, Outcome, Status
from odfa11y.families.text.spacing.candidates import spacer_candidates
from odfa11y.odf import Part
from odfa11y.odf import names as xml_names
from odfa11y.odf.allowance import Allowance, Removed
from odfa11y.odf.styles import styles_of
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.odf.styles import StyleResolver


def remove_empty_spacer_paragraphs(
    tree: etree._ElementTree,
    catalog: StyleResolver,
    removed_nodes: list[etree._Element] | None = None,
) -> int:
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
        if removed_nodes is not None:
            removed_nodes.append(paragraph)
        removed += 1
    return removed


def edit_spacers(document: OdfDocument, decision: Decision[SwitchAnswer]) -> EditResult:
    """Apply the explicitly enabled document policy."""
    if not decision.answer.enabled:
        return EditResult((
            Outcome(decision.kind.id, Status.UNCHANGED, "The reviewed policy is disabled."),
        ))
    removed_nodes = []
    count = remove_empty_spacer_paragraphs(
        document.tree(Part.CONTENT), styles_of(document), removed_nodes
    )
    return EditResult(
        (
            Outcome(
                decision.kind.id,
                Status.APPLIED if count else Status.UNCHANGED,
                f"Changed {count} source element(s).",
                count=count,
            ),
        ),
        Allowance(tuple(Removed(Part.CONTENT, node) for node in removed_nodes)),
    )
