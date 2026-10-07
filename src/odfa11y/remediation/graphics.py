# SPDX-License-Identifier: MPL-2.0
"""Give graphics accessible titles and descriptions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from lxml import etree

from odfa11y.odf import NS, qn, select_elements

from .outcome import Operation, Outcome, Status

if TYPE_CHECKING:
    from collections.abc import Mapping

    from odfa11y.odf import OdtDocument

    from .outcome import AltText


@dataclass(frozen=True, slots=True)
class SetAltText(Operation):
    """Set title/description on graphic frames matched by frame name, image path or file name."""

    entries: Mapping[str, AltText]
    name: ClassVar[str] = "set_alt_text"

    @override
    def apply(self, document: OdtDocument) -> tuple[Outcome, ...]:
        frames = select_elements(document.tree("content.xml"), "//draw:frame")
        outcomes = []
        for key, text in self.entries.items():
            matched = [frame for frame in frames if key in _frame_keys(frame)]
            if not matched:
                outcomes.append(
                    Outcome(self.name, Status.FAILED, f"No graphic matches {key!r}.", key=key)
                )
                continue
            changed = sum(_set_text(document, frame, text) for frame in matched)
            if changed:
                message = f"Set accessible text on {changed} graphic frame(s)."
                outcomes.append(Outcome(self.name, Status.APPLIED, message, key=key, count=changed))
            else:
                outcomes.append(
                    Outcome(self.name, Status.UNCHANGED, "Accessible text already set.", key=key)
                )
        return tuple(outcomes)

    @override
    def as_dict(self) -> dict[str, object]:
        return {
            "operation": self.name,
            "entries": {
                key: {"title": text.title, "description": text.description}
                for key, text in self.entries.items()
            },
        }


def _frame_keys(frame: etree._Element) -> set[str]:
    keys = {frame.get(qn("draw", "name")) or ""}
    image = frame.find("draw:image", NS)
    href = image.get(qn("xlink", "href")) if image is not None else None
    if href:
        keys |= {href, Path(href).name}
    keys.discard("")
    return keys


def _set_text(document: OdtDocument, frame: etree._Element, text: AltText) -> bool:
    changed = False
    for tag, value in ((qn("svg", "title"), text.title), (qn("svg", "desc"), text.description)):
        if value is None:
            continue
        node = frame.find(tag)
        if node is not None and (node.text or "") == value:
            continue
        document.edit("content.xml")
        if node is None:
            node = etree.Element(tag)
            frame.insert(_accessibility_position(frame, tag), node)
        node.text = value
        changed = True
    return changed


def _accessibility_position(frame: etree._Element, tag: str) -> int:
    """Find where the ODF schema allows ``svg:title`` or ``svg:desc`` in a frame.

    Returns
    -------
    int
        An index after the frame's content, with the title before the description and
        both ahead of any contour.

    """
    children = list(frame)
    title, desc = frame.find("svg:title", NS), frame.find("svg:desc", NS)
    if tag == qn("svg", "desc") and title is not None:
        return children.index(title) + 1
    if tag == qn("svg", "title") and desc is not None:
        return children.index(desc)
    fixed = {
        qn("svg", "title"),
        qn("svg", "desc"),
        qn("draw", "contour-polygon"),
        qn("draw", "contour-path"),
    }
    last_content = max(
        (index for index, child in enumerate(children) if child.tag not in fixed), default=-1
    )
    return last_content + 1
