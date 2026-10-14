# SPDX-License-Identifier: MPL-2.0
"""Resolve graphic roles and derive isolated, verifiable role styles."""

from __future__ import annotations

import base64
import hashlib
import json
from copy import deepcopy

from lxml import etree

from odfa11y.odf import NS, Part, qn

from .graphic_style_identity import (
    PREFIX,
    STYLE_ATTRIBUTES,
    _style_signature,
    normalized_role_attributes,
)
from .graphic_styles import ROLE, GraphicStyles


class GraphicRoleEditor(GraphicStyles):
    """Derive isolated role styles from an established graphic style catalog."""

    def derived(self, shape: etree._Element, *, decorative: bool) -> tuple[str, etree._Element]:
        """Clone the final cascade layer, retaining a legal common parent.

        Returns
        -------
        tuple[str, etree._Element]
            The namespace and detached target-specific style.

        """
        original = normalized_role_attributes(self.document, shape)
        shadow = deepcopy(shape)
        for attr in STYLE_ATTRIBUTES:
            shadow.attrib.pop(attr, None)
        shadow.attrib.update(original)
        ns, family, names = self.context(shadow)
        style = (
            deepcopy(self.style(family, names[-1]))
            if names
            else etree.Element(qn("style", "style"))
        )
        encoded = (
            base64
            .urlsafe_b64encode(json.dumps(original, sort_keys=True).encode())
            .decode()
            .rstrip("=")
        )
        name = (
            PREFIX
            + encoded
            + "_"
            + hashlib.sha256(shape.getroottree().getpath(shape).encode()).hexdigest()[:12]
        )
        style.set(qn("style", "name"), name)
        style.set(qn("style", "family"), family)
        props = style.find("style:graphic-properties", NS)
        if props is None:
            props = etree.Element(qn("style", "graphic-properties"))
            style.insert(0, props)
        props.set(ROLE, str(decorative).lower())
        return ns, style

    def set_role(self, shape: etree._Element, *, decorative: bool) -> bool:
        """Apply an isolated role; reuse only a proven earlier derivation.

        Returns
        -------
        bool
            Whether the source role changed.

        Raises
        ------
        ValueError
            The source context or supplied decision cannot be established safely.

        """
        if self.role(shape).decorative == decorative:
            return False
        ns, style = self.derived(shape, decorative=decorative)
        name = style.get(qn("style", "name"), "")
        family = style.get(qn("style", "family"), "")
        if self.common.get((family, name)):
            message = "Generated role style name collides with an authored common style."
            raise ValueError(message)
        found = self.automatic.get((family, name), [])
        if found:
            problem = self._existing_problem(shape, style, found)
            if problem:
                raise ValueError(problem)
            self.document.edit(Part.CONTENT)
            props = found[0].find("style:graphic-properties", NS)
            if props is None:
                props = etree.SubElement(found[0], qn("style", "graphic-properties"))
            props.set(ROLE, str(decorative).lower())
        else:
            self._adopt(style)
        self.document.edit(Part.CONTENT)
        original = normalized_role_attributes(self.document, shape)
        for attr in STYLE_ATTRIBUTES:
            shape.attrib.pop(attr, None)
        shape.attrib.update(original)
        if shape.get(qn(ns, "class-names")):
            shape.set(qn(ns, "class-names"), shape.get(qn(ns, "class-names"), "") + " " + name)
        else:
            shape.set(qn(ns, "style-name"), name)
        return True

    def change_problem(self, shape: etree._Element, *, decorative: bool) -> str | None:
        """Preflight target derivation reuse before any edit.

        Returns
        -------
        str | None
            A collision/shared-reference refusal, or None for an isolated derivation.

        """
        if self.role(shape).decorative == decorative:
            return None
        _ns, style = self.derived(shape, decorative=decorative)
        key = (style.get(qn("style", "family"), ""), style.get(qn("style", "name"), ""))
        if self.common.get(key):
            return "Generated role style name collides with an authored common style."
        found = self.automatic.get(key, [])
        return self._existing_problem(shape, style, found) if found else None

    def _existing_problem(
        self, shape: etree._Element, style: etree._Element, found: list[etree._Element]
    ) -> str | None:
        if len(found) != 1:
            return "Generated graphic style name is ambiguous."
        expected, existing = deepcopy(style), deepcopy(found[0])
        for node in (expected, existing):
            props = node.find("style:graphic-properties", NS)
            if props is not None:
                props.attrib.pop(ROLE, None)
        if _style_signature(expected) != _style_signature(existing):
            return "Generated graphic style name belongs to unproven authored content."
        name = style.get(qn("style", "name"), "")
        if any(
            node is not shape
            and any(name in node.get(attribute, "").split() for attribute in STYLE_ATTRIBUTES)
            for node in self.document.tree(Part.CONTENT).getroot().iter()
        ):
            return "A role derivation referenced by another object cannot be edited."
        return None

    def _adopt(self, style: etree._Element) -> None:
        family = style.get(qn("style", "family"), "")
        name = style.get(qn("style", "name"), "")
        root = self.document.edit(Part.CONTENT).getroot()
        auto = root.find("office:automatic-styles", NS)
        if auto is None:
            auto = etree.Element(qn("office", "automatic-styles"))
            body = root.find("office:body", NS)
            root.insert(root.index(body) if body is not None else len(root), auto)
        auto.append(style)
        self.automatic[family, name] = [style]
