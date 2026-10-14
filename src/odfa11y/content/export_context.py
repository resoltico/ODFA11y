# SPDX-License-Identifier: MPL-2.0
"""Identify declared rendering dependencies and location-sensitive document fields."""

from __future__ import annotations

from itertools import starmap
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from odfa11y.errors import PackageError, ToolFailedError
from odfa11y.odf import PackageStorage, Part, qn

from .formula_context import FormulaContext
from .formula_syntax import FormulaFacts
from .resources import ResourceIdentity, local_resource_path

if TYPE_CHECKING:
    from lxml import etree

    from odfa11y.odf import OdfDocument

MAX_EMBEDDED_OBJECTS = 64
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
    qn("presentation", "event-listener"): (qn("xlink", "href"), "event"),
    qn("form", "form"): (qn("form", "datasource"), "data-source"),
    qn("table", "source-service"): (qn("table", "name"), "data-source"),
    qn("office", "dde-source"): (qn("office", "dde-application"), "data-source"),
    qn("text", "dde-connection-decl"): (qn("office", "dde-application"), "data-source"),
    **dict.fromkeys(
        (
            qn("table", name)
            for name in ["database-source-sql", "database-source-table", "database-source-query"]
        ),
        (qn("table", "database-name"), "data-source"),
    ),
    **dict.fromkeys(
        (
            qn("text", name)
            for name in [
                "database-display",
                "database-name",
                "database-next",
                "database-row-number",
                "database-row-select",
            ]
        ),
        (qn("text", "database-name"), "data-source"),
    ),
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
    formulas = FormulaFacts()
    inspected = origins = 0
    trees, incomplete = _reachable_trees(document)
    for prefix, tree in trees:
        context = FormulaContext(tree.getroot())
        formulas += context.inspect()
        inspected += context.inspected
        origins += bool(context.inspected)
        for node in tree.iter():
            fields += node.tag == qn("text", "file-name")
            target = RESOURCE_TARGETS.get(node.tag)
            if target is not None:
                attribute, shape = target
                href = node.get(attribute, "..") if shape == "chart" else node.get(attribute)
                if href is not None:
                    local_href = (
                        _relative_href(prefix, href) if shape != "chart" or href != "." else href
                    )
                    dependencies += _unresolved(node, local_href, shape, resources)
            # Applet code/archive attributes are not single resource IRIs.
            if (
                node.tag == qn("draw", "applet")
                and any(
                    node.get(qn("draw", name)) is not None for name in ["code", "archive", "object"]
                )
                and node.get(qn("xlink", "href")) is None
            ):
                dependencies += 1
    limits = {
        "rendering_dependencies": dependencies
        + formulas.loading
        + formulas.incomplete
        + incomplete,
        "location_fields": fields + formulas.identity,
    }
    if inspected or incomplete:
        limits.update(
            formula_declarations=inspected,
            formula_origins=origins,
            formula_incomplete=formulas.incomplete + incomplete,
        )
    return limits


def _reachable_trees(
    document: OdfDocument,
) -> tuple[list[tuple[str, etree._ElementTree]], int]:
    """Follow package-local embedded ODF declarations under fixed traversal budgets.

    Returns
    -------
    tuple[list[tuple[str, etree._ElementTree]], int]
        Original parsed trees with member prefixes and incomplete inspection count.

    """
    trees = [("", tree) for tree in document.distinct_trees(Part.CONTENT, Part.STYLES, Part.META)]
    if not isinstance(document.storage, PackageStorage):
        return trees, 0
    seen: set[str] = set()
    incomplete = 0
    cursor = 0
    while cursor < len(trees):
        prefix, tree = trees[cursor]
        cursor += 1
        for node in tree.iter(qn("draw", "object")):
            path = local_resource_path(_relative_href(prefix, node.get(qn("xlink", "href"), "")))
            if path is None or path in seen:
                continue
            seen.add(path)
            if len(seen) > MAX_EMBEDDED_OBJECTS:
                return trees, incomplete + 1
            for part in ("content.xml", "styles.xml"):
                member = path + "/" + part
                if not document.storage.has(member):
                    continue
                try:
                    trees.append((path + "/", document.storage.parse_xml(member)))
                except PackageError:
                    incomplete += 1
    return trees, incomplete


def _relative_href(prefix: str, href: str) -> str:
    try:
        uri = urlsplit(href)
    except ValueError:
        return href
    return href if uri.scheme or uri.netloc or href.startswith("/") else prefix + href


def _unresolved(node: etree._Element, href: str, shape: str, resources: ResourceIdentity) -> bool:
    if shape == "event":
        # ODF action semantics: show navigates; execute launches another application.
        # Sound has its own child resource declaration; static actions do not consume href.
        return node.get(qn("presentation", "action")) == "execute"
    if shape == "data-source":
        return bool(href)  # Named/IRI bindings are unestablished; empty binds no concrete source.
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
            "Native export refuses external or unresolved rendering dependencies "
            "or formula context; "
            "use source-only inspect and embed/review required resources in the native application"
        )
        raise ToolFailedError(msg)
    if captured_identity and limits["location_fields"]:
        msg = (
            "Pipeline native export refuses filename/path fields because private staging cannot "
            "preserve their logical identity; use source-only inspect or direct original export"
        )
        raise ToolFailedError(msg)
