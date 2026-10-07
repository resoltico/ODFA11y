# SPDX-License-Identifier: MPL-2.0
"""Wrap visible addresses in hyperlinks without changing their text."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from lxml import etree

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.odf import Family, Part, qn, select_elements

from .links import URI_RE, split_trailing_punctuation
from .prose import prose_slots

if TYPE_CHECKING:
    from odfa11y.odf import OdfDocument


@dataclass(frozen=True, slots=True)
class LinkifyAddresses(Operation):
    """Turn visible URLs and email addresses into hyperlinks that keep their text."""

    name: ClassVar[str] = "linkify_addresses"
    family: ClassVar[Family | None] = Family.TEXT

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        count = linkify_plain_addresses(document.tree(Part.CONTENT))
        if not count:
            return (Outcome(self.name, Status.UNCHANGED, "No plain addresses remain."),)
        document.edit(Part.CONTENT)
        return (Outcome(self.name, Status.APPLIED, f"Created {count} hyperlink(s).", count=count),)


def linkify_plain_addresses(tree: etree._ElementTree) -> int:
    """Wrap visible addresses in hyperlinks without changing their text.

    Returns
    -------
    int
        The number of inserted hyperlink elements.

    """
    count = 0
    for block in select_elements(tree, "//office:body//text:p | //office:body//text:h"):
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
        link = etree.Element(qn("text", "a"))
        link.set(qn("xlink", "type"), "simple")
        link.set(qn("xlink", "href"), href)
        link.text = token
        next_start = matches[idx + 1].start() if idx + 1 < len(matches) else len(value)
        link.tail = punctuation + value[match.end() : next_start]
        parent.insert(insert_at, link)
        insert_at += 1
        inserted.append(link)
    return len(inserted)
