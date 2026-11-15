# SPDX-License-Identifier: MPL-2.0
"""Wrap visible addresses in hyperlinks without changing their text."""

from lxml import etree

from odfa11y.decisions import Decision
from odfa11y.decisions.answers import SwitchAnswer
from odfa11y.decisions.edit import Outcome, Status
from odfa11y.families.text.contexts import text_nodes
from odfa11y.families.text.links.prose import prose_slots
from odfa11y.families.text.links.urls import URI_RE, split_trailing_punctuation
from odfa11y.odf import Part
from odfa11y.odf import names as xml_names
lazy from odfa11y.odf import OdfDocument


def linkify_plain_addresses(tree: etree._ElementTree) -> int:
    """Wrap visible addresses in hyperlinks without changing their text.

    Returns
    -------
    int
        The number of inserted hyperlink elements.

    """
    count = 0
    for block in text_nodes(tree, xml_names.TEXT_P, xml_names.TEXT_H):
        # Collect the slots first: inserting links mutates the tree while we walk it.
        for owner, attr in list(prose_slots(block)):
            count += _linkify_slot(owner, attr)
    return count


def _linkify_slot(owner: etree._Element, attr: str) -> int:
    value = getattr(owner, attr)
    if not value:
        return 0
    matches = list(URI_RE.finditer(value))
    if not matches:
        return 0

    # Build alternating text + hyperlink elements. The first text remains in the
    # original slot, each link's tail carries the text that follows it.
    first = value[: matches[0].start()]
    setattr(owner, attr, first)
    if attr == "text":
        parent = owner
        insert_at = 0
    else:
        parent = owner.getparent()
        if parent is None:
            return 0
        insert_at = parent.index(owner) + 1

    inserted: list[etree._Element] = []
    for idx, match in enumerate(matches):
        raw = match.group(0)
        token, punctuation = split_trailing_punctuation(raw)
        href = f"mailto:{token}" if match.group("email") else token
        link = etree.Element(xml_names.TEXT_A)
        link.set(xml_names.XLINK_TYPE, "simple")
        link.set(xml_names.XLINK_HREF, href)
        link.text = token
        next_start = matches[idx + 1].start() if idx + 1 < len(matches) else len(value)
        link.tail = punctuation + value[match.end() : next_start]
        parent.insert(insert_at, link)
        insert_at += 1
        inserted.append(link)
    return len(inserted)


def edit_addresses(document: OdfDocument, decision: Decision[SwitchAnswer]) -> tuple[Outcome, ...]:
    """Apply the explicitly enabled document policy."""
    if not decision.answer.enabled:
        return (Outcome(decision.kind.id, Status.UNCHANGED, "The reviewed policy is disabled."),)
    count = linkify_plain_addresses(document.tree(Part.CONTENT))
    return (
        Outcome(
            decision.kind.id,
            Status.APPLIED if count else Status.UNCHANGED,
            f"Changed {count} source element(s).",
            count=count,
        ),
    )
