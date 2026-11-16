# SPDX-License-Identifier: MPL-2.0
"""Identify declared rendering dependencies and location-sensitive document fields."""

import re
from itertools import starmap
from urllib.parse import urlsplit

lazy from lxml import etree

from odfa11y.errors import DocumentRefusal, PackageError, Remedy, RemedyAction
from odfa11y.odf import PackageStorage, Part, qn
from odfa11y.odf import names as xml_names
from odfa11y.odf.formula import FormulaAnalysis, FormulaContext
from odfa11y.odf.resources import ResourceIdentity, local_resource_path
lazy from odfa11y.odf import OdfDocument

MAX_EMBEDDED_OBJECTS = 64
XML_BASE = xml_names.XML_BASE
URI_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
# Rendering declarations from ODF Part 3; navigation has a separate capture-context check.
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
        (xml_names.XLINK_HREF, "file"),
    ),
    xml_names.DRAW_OBJECT: (xml_names.XLINK_HREF, "object"),
    xml_names.CHART_CHART: (xml_names.XLINK_HREF, "chart"),
    xml_names.PRESENTATION_EVENT_LISTENER: (xml_names.XLINK_HREF, "event"),
    xml_names.FORM_FORM: (xml_names.FORM_DATASOURCE, "data-source"),
    xml_names.TABLE_SOURCE_SERVICE: (xml_names.TABLE_NAME, "data-source"),
    xml_names.OFFICE_DDE_SOURCE: (xml_names.OFFICE_DDE_APPLICATION, "data-source"),
    xml_names.TEXT_DDE_CONNECTION_DECL: (xml_names.OFFICE_DDE_APPLICATION, "data-source"),
    **dict.fromkeys(
        (
            qn("table", name)
            for name in ["database-source-sql", "database-source-table", "database-source-query"]
        ),
        (xml_names.TABLE_DATABASE_NAME, "data-source"),
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
        (xml_names.TEXT_DATABASE_NAME, "data-source"),
    ),
    **dict.fromkeys(
        (qn("form", name) for name in ["button", "image", "image-frame"]),
        (xml_names.FORM_IMAGE_DATA, "file"),
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
        (xml_names.XLINK_HREF, "unestablished"),
    ),
}


def native_export_limitations(document: OdfDocument) -> dict[str, int]:
    """Count unestablished resources, identity fields and location-dependent navigation.

    Ordinary navigational links are excluded. This is a narrow declaration preflight, not
    a sandbox or a proof that native importers load every embedded payload correctly.
    Explicit XML bases on render references are unsupported: the exporter has not established
    their resolution. No referenced URI is fetched.

    Returns
    -------
    dict[str, int]
        Counts of unresolved rendering dependencies and location-sensitive fields.

    """
    document.checkpoint()
    return dict(
        document.derived("native-export-context", lambda: _analyze_export_context(document))
    )


def _analyze_export_context(document: OdfDocument) -> dict[str, int]:
    resources = ResourceIdentity(document.storage)
    dependencies = fields = relative_navigation = 0
    formulas = FormulaAnalysis()
    inspected = origins = 0
    trees, incomplete = _reachable_trees(document)
    for prefix, tree in trees:
        context = FormulaContext(tree.getroot())
        formulas += context.inspect()
        inspected += context.inspected
        origins += bool(context.inspected)
        for node in tree.iter():
            fields += node.tag == xml_names.TEXT_FILE_NAME
            relative_navigation += _relative_navigation(node)
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
                node.tag == xml_names.DRAW_APPLET
                and any(
                    node.get(qn("draw", name)) is not None for name in ["code", "archive", "object"]
                )
                and node.get(xml_names.XLINK_HREF) is None
            ):
                dependencies += 1
    limits = {
        "rendering_dependencies": dependencies
        + formulas.loading
        + formulas.incomplete
        + incomplete,
        "location_fields": fields + formulas.identity,
        "relative_navigation": relative_navigation,
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
        for node in tree.iter(xml_names.DRAW_OBJECT):
            path = local_resource_path(_relative_href(prefix, node.get(xml_names.XLINK_HREF, "")))
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
        return node.get(xml_names.PRESENTATION_ACTION) == "execute"
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

    Private captures cannot preserve logical filename/path fields at the native boundary.
    Captured exports explicitly refuse those fields without rewriting authored content.
    Source-only inspection and remediation remain available.

    Raises
    ------
    DocumentRefusal
        A declared dependency or captured identity prevents established native preservation.

    """
    limits = native_export_limitations(document)
    if limits["rendering_dependencies"]:
        refusal = _resource_refusal(document)
        if refusal is not None:
            raise refusal
        msg = (
            "Native export refuses external or unresolved rendering dependencies "
            "or formula context; "
            "use source-only inspect and embed/review required resources in the native application"
        )
        raise DocumentRefusal(
            msg,
            remedy=Remedy(
                RemedyAction.EDIT_IN_APPLICATION,
                "document",
                "Review formula context and rendering dependencies.",
            ),
        )
    if captured_identity and limits["location_fields"]:
        msg = (
            "Native export refuses filename/path fields because private staging cannot "
            "preserve their logical identity; review these fields in the authoring application"
        )
        raise DocumentRefusal(
            msg,
            remedy=Remedy(
                RemedyAction.EDIT_IN_APPLICATION,
                "document",
                "Review formula context and rendering dependencies.",
            ),
        )

    if captured_identity and limits["relative_navigation"]:
        trees, _ = _reachable_trees(document)
        link = next(node for _, tree in trees for node in tree.iter() if _relative_navigation(node))
        label = link.get(xml_names.OFFICE_NAME) or link.get(xml_names.DRAW_NAME) or "hyperlink"
        message = (
            "Native export cannot preserve relative destination for "
            f"{label!r} from private staging; "
            "make the link destination absolute in the authoring application."
        )
        raise DocumentRefusal(
            message,
            remedy=Remedy(
                RemedyAction.EDIT_IN_APPLICATION,
                label,
                "Set an absolute link destination. "
                "XML base does not establish native preservation.",
            ),
        )


def _relative_navigation(node: etree._Element) -> bool:
    if node.tag not in {xml_names.TEXT_A, xml_names.DRAW_A}:
        return False
    href = node.get(xml_names.XLINK_HREF, "")
    # LibreOffice resolves these against the input location even with an XML base.
    return bool(href and not href.startswith("#") and not URI_SCHEME.match(href))


def _resource_refusal(document: OdfDocument) -> DocumentRefusal | None:
    resources = ResourceIdentity(document.storage)
    trees, _incomplete = _reachable_trees(document)
    for prefix, tree in trees:
        for index, node in enumerate(tree.iter(), 1):
            declaration = RESOURCE_TARGETS.get(node.tag)
            if declaration is None:
                continue
            attribute, shape = declaration
            href = node.get(attribute)
            if href is None or not _unresolved(
                node, _relative_href(prefix, href), shape, resources
            ):
                continue
            frame = next(node.iterancestors(xml_names.DRAW_FRAME), node)
            name = frame.get(xml_names.DRAW_NAME) or node.get(xml_names.DRAW_NAME)
            target = f"frame {name!r}" if name else f"rendering element {index}"
            try:
                resource = urlsplit(href).path.rsplit("/", 1)[-1] or "declared resource"
            except ValueError:
                resource = "malformed resource reference"
            action = (
                RemedyAction.EMBED_RESOURCE
                if shape in {"file", "object", "chart"}
                else RemedyAction.EDIT_IN_APPLICATION
            )
            message = (
                f"Native export refuses {target}: embed or review resource {resource!r} "
                "in the source application."
            )
            return DocumentRefusal(message, remedy=Remedy(action, target, resource))
    return None
