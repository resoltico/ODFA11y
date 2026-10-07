# SPDX-License-Identifier: MPL-2.0
"""Give the pictures, charts and objects in a spreadsheet accessible titles and descriptions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from lxml import etree

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.odf import NS, Family, Part, qn, select_elements

from .sheets import sheet_index

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from odfa11y.odf import OdfDocument

FINGERPRINT_LENGTH = 12
MIN_CONFLICTING_VALUES = 2
FIELDS = (("title", qn("svg", "title")), ("description", qn("svg", "desc")))
FIXED_CHILDREN = frozenset({
    qn("svg", "title"),
    qn("svg", "desc"),
    qn("draw", "contour-polygon"),
    qn("draw", "contour-path"),
})


@dataclass(frozen=True, slots=True)
class ObjectAltText:
    """Accessible text for a frame; ``None`` leaves that field untouched.

    ``fingerprint``, when given, must match the addressed frames or the entry fails: the
    object the plan was reviewed against has changed.
    """

    title: str | None = None
    description: str | None = None
    fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class SetObjectAltText(Operation):
    """Set title/description on frames matched by frame name, image path or file name."""

    entries: Mapping[str, ObjectAltText]
    name: ClassVar[str] = "set_object_alt_text"
    family: ClassVar[Family | None] = Family.SPREADSHEET

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        frames = select_elements(document.tree(Part.CONTENT), "//office:body//draw:frame")
        matched = {
            key: [frame for frame in frames if key in frame_keys(frame)] for key in self.entries
        }
        failures = self._preflight(matched)
        if failures:
            return failures
        outcomes = []
        for key, text in self.entries.items():
            changed = sum(_set_text(document, frame, text) for frame in matched[key])
            if changed:
                message = f"Set accessible text on {changed} frame(s)."
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
                key: {
                    "title": text.title,
                    "description": text.description,
                    "fingerprint": text.fingerprint,
                }
                for key, text in self.entries.items()
            },
        }

    def _preflight(self, matched: dict[str, list[etree._Element]]) -> tuple[Outcome, ...]:
        """Resolve every selector before any edit; report all problems together.

        Returns
        -------
        tuple[Outcome, ...]
            One failed outcome per selector that matches nothing, drifted, or conflicts
            with another selector on a shared frame; empty when the plan is consistent.

        """
        failures: dict[str, str] = {}
        for key, frames in matched.items():
            if not frames:
                failures[key] = f"No frame matches {key!r}."
                continue
            expected = self.entries[key].fingerprint
            if expected is not None and expected != frames_fingerprint(frames):
                failures[key] = (
                    "The addressed frame is no longer the object this plan was reviewed against."
                )
        self._find_conflicts(matched, failures)
        return tuple(
            Outcome(self.name, Status.FAILED, message, key=key) for key, message in failures.items()
        )

    def _find_conflicts(
        self, matched: dict[str, list[etree._Element]], failures: dict[str, str]
    ) -> None:
        wanted: dict[tuple[int, str], dict[str, list[str]]] = {}
        for key, frames in matched.items():
            for frame in frames:
                for label, _tag in FIELDS:
                    value = getattr(self.entries[key], label)
                    if value is not None:
                        wanted.setdefault((id(frame), label), {}).setdefault(value, []).append(key)
        for (_frame, label), values in wanted.items():
            if len(values) < MIN_CONFLICTING_VALUES:
                continue
            keys = sorted({key for owners in values.values() for key in owners})
            for key in keys:
                others = ", ".join(repr(other) for other in keys if other != key)
                failures.setdefault(
                    key, f"Sets a different {label} than {others} on the same frame."
                )


def frame_keys(frame: etree._Element) -> set[str]:
    """List the selectors that address a frame.

    Returns
    -------
    set[str]
        The frame name, the image reference and the image file name.

    """
    keys = {frame.get(qn("draw", "name")) or ""}
    image = frame.find("draw:image", NS)
    href = image.get(qn("xlink", "href")) if image is not None else None
    if href:
        keys |= {href, Path(href).name}
    keys.discard("")
    return keys


def frames_fingerprint(frames: Sequence[etree._Element]) -> str:
    """Fingerprint the frames a selector addresses.

    The digest covers facts no operation changes (name, image file, size and the position of
    the frame's sheet, not its name), so renaming sheets keeps it valid.

    Returns
    -------
    str
        A short hexadecimal digest.

    """
    facts = [_frame_facts(frame) for frame in frames]
    payload = json.dumps(facts, ensure_ascii=True, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:FINGERPRINT_LENGTH]


def _frame_facts(frame: etree._Element) -> list[str | int | None]:
    image = frame.find("draw:image", NS)
    href = image.get(qn("xlink", "href")) if image is not None else None
    return [
        frame.get(qn("draw", "name")),
        Path(href).name if href else None,
        frame.get(qn("svg", "width")),
        frame.get(qn("svg", "height")),
        sheet_index(frame),
    ]


def _set_text(document: OdfDocument, frame: etree._Element, text: ObjectAltText) -> bool:
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
    last_content = max(
        (index for index, child in enumerate(children) if child.tag not in FIXED_CHILDREN),
        default=-1,
    )
    return last_content + 1
