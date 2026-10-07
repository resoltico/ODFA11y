# SPDX-License-Identifier: MPL-2.0
"""Ephemeral selector, position and payload identities for graphic review."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.odf import NS, qn, select_elements

from .resources import ResourceIdentity
from .tables import AXES, declarations, repeated
from .xml import protected_xml

if TYPE_CHECKING:
    from collections.abc import Sequence

    from lxml import etree

    from odfa11y.odf import OdfDocument


def graphic_keys(frame: etree._Element) -> set[str]:
    """List selectors by frame name, image URI and image file name.

    Returns
    -------
    set[str]
        Non-empty selector strings.

    """
    keys = {frame.get(qn("draw", "name")) or ""}
    image = frame.find("draw:image", NS)
    href = image.get(qn("xlink", "href")) if image is not None else None
    if href:
        keys |= {href, Path(href).name}
    keys.discard("")
    return keys


class GraphicIdentity:
    """Read-only audit/preflight snapshot; discard before document or storage mutations."""

    def __init__(self, document: OdfDocument, frames: Sequence[etree._Element]) -> None:
        """Index selectors once; compute protected structure and payload hashes only on demand."""
        grouped: dict[str, list[etree._Element]] = {}
        for frame in frames:
            for key in graphic_keys(frame):
                grouped.setdefault(key, []).append(frame)
        self._groups = {key: tuple(group) for key, group in grouped.items()}
        self._registered = {id(group) for group in self._groups.values()}
        self._resources = ResourceIdentity(document.storage)
        self._facts: dict[etree._Element, list[object]] = {}
        self._group_digests: dict[int, str] = {}
        self._sibling_ordinals: dict[etree._Element, dict[etree._Element, int]] = {}
        self._table_ordinals: dict[tuple[etree._Element, str], dict[etree._Element, int]] = {}

    def matching(self, selector: str) -> tuple[etree._Element, ...]:
        """Return the immutable, document-ordered group addressed by a selector.

        Returns
        -------
        tuple[etree._Element, ...]
            Matching graphics, or an empty tuple when the selector is absent.

        """
        return self._groups.get(selector, ())

    def fingerprint(self, frames: Sequence[etree._Element]) -> str:
        """Hash an ordered selection, retaining payload names, bytes and protected XML facts.

        Returns
        -------
        str
            A digest independent of mutable accessible-description metadata.

        """
        group = id(frames)
        if group in self._registered and group in self._group_digests:
            return self._group_digests[group]
        facts = [self._frame(frame) for frame in frames]
        digest = hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()[:16]
        if group in self._registered:
            self._group_digests[group] = digest
        return digest

    def _frame(self, frame: etree._Element) -> list[object]:
        if frame not in self._facts:
            payloads = [
                self._resources.fingerprint(node.get(qn("xlink", "href"), ""))
                for node in select_elements(frame, ".//*[@xlink:href]")
            ]
            self._facts[frame] = [
                self._position(frame),
                protected_xml(frame, omitted_elements=(qn("svg", "title"), qn("svg", "desc"))),
                payloads,
            ]
        return self._facts[frame]

    def _position(self, node: etree._Element) -> list[tuple[str, int]]:
        path = []
        while node.getparent() is not None and node.tag != qn("office", "body"):
            parent = node.getparent()
            if parent is None:
                break
            if node.tag not in {
                qn("table", "table-header-rows"),
                qn("table", "table-header-columns"),
            }:
                path.append((str(node.tag), self._ordinal(node, parent)))
            node = parent
        return path

    def _ordinal(self, node: etree._Element, parent: etree._Element) -> int:
        axis = next((key for key, value in AXES.items() if node.tag == qn("table", value[0])), None)
        table = next(node.iterancestors(qn("table", "table")), None) if axis else None
        if axis is not None and table is not None:
            key = (table, axis)
            if key not in self._table_ordinals:
                total = 0
                ordinals = {}
                for declaration in declarations(table, axis):
                    ordinals[declaration] = total
                    total += repeated(declaration, AXES[axis][2])
                self._table_ordinals[key] = ordinals
            return self._table_ordinals[key][node]
        if parent not in self._sibling_ordinals:
            counts: dict[object, int] = {}
            ordinals = {}
            for child in parent:
                ordinals[child] = counts.get(child.tag, 0)
                counts[child.tag] = ordinals[child] + 1
            self._sibling_ordinals[parent] = ordinals
        return self._sibling_ordinals[parent][node]


def graphics_fingerprint(document: OdfDocument, frames: Sequence[etree._Element]) -> str:
    """Compute a fresh graphic review identity, never caching mutable document state.

    Returns
    -------
    str
        Selection digest independent of its accessible-description metadata.

    """
    return GraphicIdentity(document, frames).fingerprint(frames)
