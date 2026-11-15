# SPDX-License-Identifier: MPL-2.0
"""Ephemeral selector, position and payload identities for graphic review."""

import json
from collections import Counter
from urllib.parse import quote
lazy from collections.abc import Sequence

lazy from lxml import etree

from odfa11y.concepts.graphic_styles import (
    GraphicRoles,
    graphic_normalization,
    graphic_style_fingerprint,
)
from odfa11y.concepts.tables import AXES, declarations, repeated
from odfa11y.concepts.text import reading_context_path
from odfa11y.decisions import DecisionKind, OpenDecision
from odfa11y.errors import DocumentRefusal
from odfa11y.odf import NS, qn, select_elements
from odfa11y.odf import names as xml_names
from odfa11y.odf.canonical import protected_xml
from odfa11y.odf.resources import ResourceIdentity
from odfa11y.odf.styles import normalize_generated
from odfa11y.report import Location
from odfa11y.targets import Fingerprint, Target
lazy from odfa11y.odf import OdfDocument

SHAPE_TAGS = (
    *(
        qn("draw", name)
        for name in (
            "frame",
            "rect",
            "ellipse",
            "line",
            "path",
            "polygon",
            "polyline",
            "regular-polygon",
            "custom-shape",
            "connector",
            "measure",
            "g",
            "caption",
            "circle",
            "page-thumbnail",
            "control",
        )
    ),
    xml_names.DR3D_SCENE,
)


STYLE_CONTENT_TAGS = frozenset({
    *SHAPE_TAGS,
    xml_names.DRAW_PAGE,
    *(qn("dr3d", name) for name in ("cube", "sphere", "extrude", "rotate")),
})


def graphic_selector(frame: etree._Element) -> str | None:
    """Qualify an authored graphic name or image reference by current text context.

    Returns
    -------
    str | None
        A canonical logical selector, or None when native identity must be established.

    """
    context = reading_context_path(frame)
    if name := frame.get(xml_names.DRAW_NAME):
        return f"{context}/frame[name={quote(name, safe='')}]"
    return None


class GraphicIdentity:
    """Read-only audit/preflight snapshot; discard before document or storage mutations."""

    def __init__(self, document: OdfDocument, frames: Sequence[etree._Element]) -> None:
        """Index selectors once; compute protected structure and payload hashes only on demand."""
        grouped: dict[str, list[etree._Element]] = {}
        self._targets: dict[etree._Element, str] = {}
        positions: dict[str, int] = {}
        selectors = Counter(graphic_selector(frame) for frame in frames)
        for frame in frames:
            if frame.tag == xml_names.DRAW_G:
                continue
            context = reading_context_path(frame)
            if frame.tag != xml_names.DRAW_G:
                positions[context] = positions.get(context, 0) + 1
            selector = graphic_selector(frame)
            target = (
                selector
                if selector and selectors[selector] == 1
                else (f"{context}/frame[{positions.get(context, 1)}]")
            )
            self._targets[frame] = target
            grouped.setdefault(target, []).append(frame)
        self._document = document
        self._groups = {key: tuple(group) for key, group in grouped.items()}
        self._registered = {id(group) for group in self._groups.values()}
        self._resources = ResourceIdentity(document.storage)
        self._facts: dict[etree._Element, list[object]] = {}
        self._style_facts: dict[etree._Element, str] = {}
        self._style_problems: dict[etree._Element, str | None] = {}
        self._styles = GraphicRoles(document)
        self._group_digests: dict[int, Fingerprint] = {}
        self._sibling_ordinals: dict[etree._Element, dict[etree._Element, int]] = {}
        self._table_ordinals: dict[tuple[etree._Element, str], dict[etree._Element, int]] = {}

    def target(self, frame: etree._Element) -> str:
        """Return the canonical name/ordinal path used by both audit and operations.

        Returns
        -------
        str
            The graphic's reviewed logical target.

        """
        return self._targets[frame]

    def open_decision(self, frame: etree._Element, kind: DecisionKind) -> OpenDecision:
        """Collect an explicit graphic question using the existing identity snapshot.

        Returns
        -------
        OpenDecision
            One reviewed group identity and its current authored alternatives.

        """
        target = self.target(frame)
        group = self.matching(target)
        current = {
            "title": [node.findtext("svg:title", namespaces=NS) for node in group],
            "description": [node.findtext("svg:desc", namespaces=NS) for node in group],
            "count": len(group),
        }
        return OpenDecision(
            kind,
            Target((Location(target)).path, Fingerprint(self.fingerprint(group))),
            current,
        )

    def matching(self, selector: str) -> tuple[etree._Element, ...]:
        """Return the immutable, document-ordered group addressed by a selector.

        Returns
        -------
        tuple[etree._Element, ...]
            Matching graphics, or an empty tuple when the selector is absent.

        """
        return self._groups.get(selector, ())

    def fingerprint(self, frames: Sequence[etree._Element]) -> Fingerprint:
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
        digest = Fingerprint.of(json.dumps(facts, sort_keys=True).encode())
        if group in self._registered:
            self._group_digests[group] = digest
        return digest

    def _frame(self, frame: etree._Element) -> list[object]:
        if frame not in self._facts:
            payloads = [
                self._resources.fingerprint(node.get(xml_names.XLINK_HREF, ""))
                for node in select_elements(frame, ".//*[@xlink:href]")
            ]
            self._facts[frame] = [
                self.logical_position(frame),
                self.style_dependencies(frame),
                protected_xml(
                    normalize_generated(frame, graphic_normalization(self._document)),
                    omitted_elements=(xml_names.SVG_TITLE, xml_names.SVG_DESC),
                    omitted_element_attributes={
                        qn(ns, "a"): (xml_names.OFFICE_TITLE,) for ns in ("draw", "text")
                    },
                ),
                payloads,
            ]
        return self._facts[frame]

    def style_dependencies(self, root: etree._Element) -> tuple[str, ...]:
        """Bind the effective visual style dependencies of each graphical descendant.

        Returns
        -------
        tuple[str, ...]
            Source-ordered root/shape style facts, excluding only proven role derivations.

        """
        nodes = [node for node in root.iter() if node.tag in STYLE_CONTENT_TAGS]
        for node in nodes:
            if node not in self._style_facts:
                self._read_style(node)
        return tuple(self._style_facts[node] for node in nodes)

    def style_problem(self, root: etree._Element) -> str | None:
        """Refuse metadata decisions when their subtree's visual dependencies are unresolved.

        Returns
        -------
        str | None
            The first unresolved source style context, or None for bound dependencies.

        """
        self.style_dependencies(root)
        return next(
            (self._style_problems[node] for node in root.iter() if self._style_problems.get(node)),
            None,
        )

    def _read_style(self, node: etree._Element) -> None:
        try:
            self._style_facts[node] = graphic_style_fingerprint(self._document, node)
            problem = None
        except DocumentRefusal as error:
            self._style_facts[node] = "unresolved"
            problem = str(error)
        if node.tag != xml_names.DRAW_PAGE:
            problem = problem or self._styles.role(node).problem
        self._style_problems[node] = problem

    def logical_position(self, node: etree._Element) -> list[tuple[str, int]]:
        """Bind source order independently of storage and reviewed header wrappers.

        Returns
        -------
        list[tuple[str, int]]
            Qualified XML steps and logical ordinals, ending at the current body.

        """
        path = []
        while node.getparent() is not None and node.tag != xml_names.OFFICE_BODY:
            parent = node.getparent()
            if parent is None:
                break
            if node.tag not in {
                xml_names.TABLE_TABLE_HEADER_ROWS,
                xml_names.TABLE_TABLE_HEADER_COLUMNS,
            }:
                path.append((str(node.tag), self._ordinal(node, parent)))
            node = parent
        return path

    def _ordinal(self, node: etree._Element, parent: etree._Element) -> int:
        axis = next((key for key, value in AXES.items() if node.tag == qn("table", value[0])), None)
        table = next(node.iterancestors(xml_names.TABLE_TABLE), None) if axis else None
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


def graphics_fingerprint(document: OdfDocument, frames: Sequence[etree._Element]) -> Fingerprint:
    """Compute a fresh graphic review identity, never caching mutable document state.

    Returns
    -------
    str
        Selection digest independent of its accessible-description metadata.

    """
    return GraphicIdentity(document, frames).fingerprint(frames)


def graphic_style_dependencies(document: OdfDocument, root: etree._Element) -> tuple[str, ...]:
    """Bind a subtree to every descendant shape's referenced visual properties.

    Returns
    -------
    tuple[str, ...]
        Fresh style identities; no cached mutable document state is retained.

    """
    return GraphicIdentity(document, ()).style_dependencies(root)
