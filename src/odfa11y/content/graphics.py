# SPDX-License-Identifier: MPL-2.0
"""Give graphics accessible titles and descriptions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lxml import etree

from odfa11y.adapter import Outcome, Status
from odfa11y.odf import NS, Part, qn, select_elements

if TYPE_CHECKING:
    from collections.abc import Mapping

    from odfa11y.odf import OdfDocument

from .graphic_identity import GraphicIdentity

MIN_CONFLICTING_VALUES = 2
FIELDS = (("title", qn("svg", "title")), ("description", qn("svg", "desc")))


@dataclass(frozen=True, slots=True)
class GraphicDescription:
    """Accessible text for a graphic; ``None`` leaves that field untouched.

    ``fingerprint``, when given, must match the addressed graphics or the entry fails: the
    object the plan was reviewed against has changed.
    """

    title: str | None = None
    description: str | None = None
    fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class GraphicEditor:
    """Set title/description on graphic frames matched by frame name, image path or file name."""

    entries: Mapping[str, GraphicDescription]
    name: str
    shape_tags: tuple[str, ...] = (qn("draw", "frame"),)

    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        """Preflight every graphic target, then edit description metadata.

        Returns
        -------
        tuple[Outcome, ...]
            Per-target results, with no edit when any target fails.

        """
        tags = set(self.shape_tags)
        frames = [
            node
            for node in select_elements(document.tree(Part.CONTENT), "//office:body//*")
            if node.tag in tags
        ]
        identity = GraphicIdentity(document, frames)
        matched = {key: identity.matching(key) for key in self.entries}
        failures = self._preflight(identity, matched)
        if failures:
            return failures
        outcomes = []
        for key, text in self.entries.items():
            changed = sum(set_description(document, frame, text) for frame in matched[key])
            if changed:
                message = f"Set accessible text on {changed} graphic frame(s)."
                outcomes.append(Outcome(self.name, Status.APPLIED, message, key=key, count=changed))
            else:
                outcomes.append(
                    Outcome(self.name, Status.UNCHANGED, "Accessible text already set.", key=key)
                )
        return tuple(outcomes)

    def _preflight(
        self, identity: GraphicIdentity, matched: dict[str, tuple[etree._Element, ...]]
    ) -> tuple[Outcome, ...]:
        """Resolve every selector before any edit; report all problems together.

        Returns
        -------
        tuple[Outcome, ...]
            One failed outcome per selector that matches nothing, drifted, or conflicts
            with another selector on a shared graphic; empty when the plan is consistent.

        """
        failures: dict[str, str] = {}
        for key, frames in matched.items():
            entry = self.entries[key]
            if any(
                value is not None and not isinstance(value, str)
                for value in (entry.title, entry.description, entry.fingerprint)
            ):
                failures[key] = "Graphic title, description and fingerprint must be strings."
                continue
            if not frames:
                failures[key] = f"No graphic matches {key!r}."
                continue
            expected = entry.fingerprint
            if expected is not None and expected != identity.fingerprint(frames):
                failures[key] = (
                    "The addressed graphic is no longer the object this plan was reviewed against."
                )
        self._find_conflicts(matched, failures)
        return tuple(
            Outcome(self.name, Status.FAILED, message, key=key) for key, message in failures.items()
        )

    def _find_conflicts(
        self, matched: dict[str, tuple[etree._Element, ...]], failures: dict[str, str]
    ) -> None:
        wanted: dict[tuple[int, str], dict[str, list[str]]] = {}
        for key, frames in matched.items():
            for frame in frames:
                for label, _tag in FIELDS:
                    value = getattr(self.entries[key], label)
                    if isinstance(value, str):
                        wanted.setdefault((id(frame), label), {}).setdefault(value, []).append(key)
        for (_frame, label), values in wanted.items():
            if len(values) < MIN_CONFLICTING_VALUES:
                continue
            keys = sorted({key for owners in values.values() for key in owners})
            for key in keys:
                others = ", ".join(repr(other) for other in keys if other != key)
                failures.setdefault(
                    key, f"Sets a different {label} than {others} on the same graphic."
                )


def set_description(document: OdfDocument, frame: etree._Element, text: GraphicDescription) -> bool:
    """Edit supplied description fields in the standard order for the element.

    Returns
    -------
    bool
        Whether any description field changed.

    """
    changed = False
    for label, tag in FIELDS:
        value = getattr(text, label)
        if value is None:
            continue
        node = frame.find(tag)
        if node is not None and (node.text or "") == value:
            continue
        document.edit(Part.CONTENT)
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
    if frame.tag != qn("draw", "frame"):
        return int(bool(children and children[0].tag == qn("office", "event-listeners")))
    last_content = max(
        (index for index, child in enumerate(children) if child.tag not in fixed), default=-1
    )
    return last_content + 1
