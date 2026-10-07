# SPDX-License-Identifier: MPL-2.0
"""Wrap visible addresses in hyperlinks without changing their text."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from lxml import etree

from odfa11y.odf import URI_RE, qn, select_elements, split_trailing_punctuation

from .outcome import Operation, Outcome, Status

if TYPE_CHECKING:
    from odfa11y.odf import OdtDocument


@dataclass(frozen=True, slots=True)
class LinkifyAddresses(Operation):
    """Turn visible URLs and email addresses into hyperlinks that keep their text."""

    name: ClassVar[str] = "linkify_addresses"

    @override
    def apply(self, document: OdtDocument) -> tuple[Outcome, ...]:
        count = linkify_plain_addresses(document.tree("content.xml"))
        if not count:
            return (Outcome(self.name, Status.UNCHANGED, "No plain addresses remain."),)
        document.edit("content.xml")
        return (Outcome(self.name, Status.APPLIED, f"Created {count} hyperlink(s).", count=count),)


def linkify_plain_addresses(tree: etree._ElementTree) -> int:
    """Wrap visible addresses in hyperlinks without changing their text.

    Returns
    -------
    int
        The number of inserted hyperlink elements.

    """
    count = 0
    blocks = select_elements(tree, "//text:p | //text:h")
    for block in blocks:
        # Traverse a stable list because link insertion mutates the tree.
        for element in list(block.iter()):
            if element.tag == qn("text", "a") or _has_ancestor_link(element):
                continue
            if element.text:
                count += _linkify_slot(element, "text")
            for child in list(element):
                # A child's tail is outside that child, including when child is a link.
                if child.tail and not _has_ancestor_link(element):
                    count += _linkify_slot(child, "tail")
    return count


def _has_ancestor_link(element: etree._Element) -> bool:
    return bool(select_elements(element, "ancestor::text:a"))


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
