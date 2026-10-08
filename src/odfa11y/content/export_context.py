# SPDX-License-Identifier: MPL-2.0
"""Identify declared rendering dependencies and location-sensitive document fields."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.errors import ToolFailedError
from odfa11y.odf import Part, qn

from .resources import ResourceIdentity

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument

XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"
RENDER_REFERENCES = frozenset({
    qn("draw", "image"),
    qn("draw", "object"),
    qn("draw", "object-ole"),
    qn("draw", "plugin"),
    qn("draw", "floating-frame"),
    qn("style", "background-image"),
    qn("svg", "font-face-uri"),
    qn("text", "section-source"),
    qn("text", "alphabetical-index-auto-mark-file"),
    qn("table", "table-source"),
    qn("table", "cell-range-source"),
})


def native_export_limitations(document: OdfDocument) -> dict[str, int]:
    """Count known render references outside embedded storage and filename/path fields.

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
    for tree in document.distinct_trees(Part.CONTENT, Part.STYLES):
        for node in tree.iter():
            fields += node.tag == qn("text", "file-name")
            href = node.get(qn("xlink", "href"))
            if node.tag in RENDER_REFERENCES and href is not None:
                dependencies += _explicit_base(node) or not resources.available(href)
    return {"rendering_dependencies": dependencies, "location_fields": fields}


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
