# SPDX-License-Identifier: MPL-2.0
"""Wrap visible addresses in hyperlinks without changing their text."""

from dataclasses import dataclass
from typing import ClassVar, override

from lxml import etree

from odfa11y.concepts.edits import Operation, Outcome, Status
from odfa11y.families.text.contexts import text_nodes
from odfa11y.families.text.links.prose import prose_slots
from odfa11y.families.text.links.urls import URI_RE, split_trailing_punctuation
from odfa11y.odf import Family, Part
from odfa11y.odf import names as xml_names
lazy from odfa11y.odf import OdfDocument


@dataclass(frozen=True, slots=True)
class LinkifyAddresses(Operation):
    """Turn visible URLs and email addresses into hyperlinks that keep their text."""

    name: ClassVar[str] = "linkify_addresses"
    families: ClassVar[frozenset[Family] | None] = frozenset({Family.TEXT})

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        count = linkify_plain_addresses(document.tree(Part.CONTENT))
        if not count:
            return (Outcome(self.name, Status.UNCHANGED, "No plain addresses remain."),)
        return (Outcome(self.name, Status.APPLIED, f"Created {count} hyperlink(s).", count=count),)


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
