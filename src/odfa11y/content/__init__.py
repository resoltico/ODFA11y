# SPDX-License-Identifier: MPL-2.0
"""Shared ODF content vocabulary, without document-family decisions."""

from .export_context import native_export_limitations, require_native_context
from .graphic_identity import GraphicIdentity, graphic_keys, graphic_selector, graphics_fingerprint
from .graphic_style_identity import normalized_graphic_tree, normalized_role_attributes
from .graphic_styles import audit_graphic_role, effective_graphic_role
from .graphics import GraphicAlternative, GraphicEditor, set_description
from .language import set_style_language, style_language
from .links import (
    LinkDescription,
    LinkEditor,
    document_links,
    link_decision,
    link_fingerprint,
    link_has_description,
    link_location,
)
from .locations import page_location, sheet_location
from .pages import (
    SHAPE_TAGS,
    PageDecision,
    PageEditor,
    navigation_problem,
    page_fingerprint,
    page_shapes,
    page_snapshot,
    pages,
    shape_identity,
)
from .protection import opaque_payloads
from .resources import local_resource_path
from .table_identity import table_content_fingerprint, table_fingerprint
from .tables import (
    AXES,
    axis_count,
    cell_at,
    declarations,
    header_count,
    repeated,
    require_safe_boundary,
)
from .text import eligible_text_node, reading_context_path, visible_words
from .xml import protected_xml

__all__ = [
    "AXES",
    "SHAPE_TAGS",
    "GraphicAlternative",
    "GraphicEditor",
    "GraphicIdentity",
    "LinkDescription",
    "LinkEditor",
    "PageDecision",
    "PageEditor",
    "audit_graphic_role",
    "axis_count",
    "cell_at",
    "declarations",
    "document_links",
    "effective_graphic_role",
    "eligible_text_node",
    "graphic_keys",
    "graphic_selector",
    "graphics_fingerprint",
    "header_count",
    "link_decision",
    "link_fingerprint",
    "link_has_description",
    "link_location",
    "local_resource_path",
    "native_export_limitations",
    "navigation_problem",
    "normalized_graphic_tree",
    "normalized_role_attributes",
    "opaque_payloads",
    "page_fingerprint",
    "page_location",
    "page_shapes",
    "page_snapshot",
    "pages",
    "protected_xml",
    "reading_context_path",
    "repeated",
    "require_native_context",
    "require_safe_boundary",
    "set_description",
    "set_style_language",
    "shape_identity",
    "sheet_location",
    "style_language",
    "table_content_fingerprint",
    "table_fingerprint",
    "visible_words",
]
