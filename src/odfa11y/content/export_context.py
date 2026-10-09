# SPDX-License-Identifier: MPL-2.0
"""Identify declared rendering dependencies and location-sensitive document fields."""

from __future__ import annotations

from itertools import starmap
from typing import TYPE_CHECKING

from odfa11y.errors import ToolFailedError
from odfa11y.odf import Part, qn

from .resources import ResourceIdentity

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument

XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"
# Attribute and addressing contract from ODF Part 3; navigation is deliberately absent.
# Unestablished dynamic import/execution declarations are refused even for internal URIs.
RESOURCE_TARGETS = {
    **dict.fromkeys(
        starmap(
            qn,
            [
                ("draw", "image"),
                ("draw", "fill-image"),
                ("draw", "object-ole"),
                ("draw", "plugin"),
                ("draw", "floating-frame"),
                ("style", "background-image"),
                ("text", "list-level-style-image"),
                ("chart", "symbol-image"),
                ("svg", "definition-src"),
                ("svg", "font-face-uri"),
                ("text", "section-source"),
                ("text", "alphabetical-index-auto-mark-file"),
                ("table", "table-source"),
                ("table", "cell-range-source"),
                ("anim", "audio"),
                ("presentation", "sound"),
            ],
        ),
        (qn("xlink", "href"), "file"),
    ),
    qn("draw", "object"): (qn("xlink", "href"), "object"),
    qn("chart", "chart"): (qn("xlink", "href"), "chart"),
    **dict.fromkeys(
        (qn("form", name) for name in ["button", "image", "image-frame"]),
        (qn("form", "image-data"), "file"),
    ),
    **dict.fromkeys(
        starmap(
            qn,
            [
                ("form", "connection-resource"),
                ("draw", "applet"),
                ("text", "script"),
                ("script", "event-listener"),
                ("presentation", "event-listener"),
                ("meta", "auto-reload"),
            ],
        ),
        (qn("xlink", "href"), "unestablished"),
    ),
}


def native_export_limitations(document: OdfDocument) -> dict[str, int]:
    """Count unresolved/unestablished declared resources and filename/path fields.

    Ordinary navigational links are excluded. This is a narrow declaration preflight, not
    a sandbox or a proof that native importers load every embedded payload correctly.
    Explicit XML bases on render references are unsupported: the exporter has not established
    their resolution. No referenced URI is fetched.

    Returns
    -------
    dict[str, int]
        Counts of unresolved rendering dependencies and location-sensitive fields.

    """
    resources = ResourceIdentity(document.storage)
    dependencies = fields = 0
    for tree in document.distinct_trees(Part.CONTENT, Part.STYLES, Part.META):
        for node in tree.iter():
            fields += node.tag == qn("text", "file-name")
            target = RESOURCE_TARGETS.get(node.tag)
            if target is not None:
                attribute, shape = target
                href = node.get(attribute, "..") if shape == "chart" else node.get(attribute)
                if href is not None:
                    dependencies += _unresolved(node, href, shape, resources)
            # Applet code/archive attributes are not single resource IRIs.
            if (
                node.tag == qn("draw", "applet")
                and any(
                    node.get(qn("draw", name)) is not None for name in ["code", "archive", "object"]
                )
                and node.get(qn("xlink", "href")) is None
            ):
                dependencies += 1
    return {"rendering_dependencies": dependencies, "location_fields": fields}


def _unresolved(node: etree._Element, href: str, shape: str, resources: ResourceIdentity) -> bool:
    if _explicit_base(node) or shape == "unestablished":
        return True
    if shape == "chart" and href == ".":
        return False  # Normative self-data context, not a file/directory address.
    return not resources.available(href, object_directory=shape in {"object", "chart"})


def _explicit_base(node: etree._Element) -> bool:
    return bool(node.get(XML_BASE)) or any(parent.get(XML_BASE) for parent in node.iterancestors())


def require_native_context(document: OdfDocument, *, captured_identity: bool = False) -> None:
    """Refuse unsupported render dependencies or a captured input's location-sensitive fields.

    Direct original exports may retain their logical filename/path. Pipeline captures cannot
    do so at the current native boundary and explicitly refuse those fields without rewriting
    authored content. Source-only inspection/remediation remains available.

    Raises
    ------
    ToolFailedError
        A declared dependency or captured identity prevents established native preservation.

    """
    limits = native_export_limitations(document)
    if limits["rendering_dependencies"]:
        msg = (
            "Native export refuses external or unresolved rendering dependencies; "
            "use source-only inspect and embed/review required resources in the native application"
        )
        raise ToolFailedError(msg)
    if captured_identity and limits["location_fields"]:
        msg = (
            "Pipeline native export refuses filename/path fields because private staging cannot "
            "preserve their logical identity; use source-only inspect or direct original export"
        )
        raise ToolFailedError(msg)
