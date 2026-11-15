# SPDX-License-Identifier: MPL-2.0
"""Shared ODF content vocabulary, without document-family decisions."""

from odfa11y.concepts.graphic_identity import (
    GraphicIdentity,
    graphic_selector,
    graphics_fingerprint,
)
from odfa11y.concepts.graphic_styles import (
    audit_graphic_role,
    effective_graphic_role,
    normalized_graphic_tree,
    normalized_role_attributes,
)
from odfa11y.concepts.graphics import set_description
from odfa11y.concepts.language import CHANNEL_ATTRIBUTES, set_style_language, style_language
from odfa11y.concepts.links import (
    document_links,
    link_decision,
    link_fingerprint,
    link_has_description,
    link_location,
)
from odfa11y.concepts.locations import page_location, sheet_location
from odfa11y.concepts.pages import (
    SHAPE_TAGS,
    navigation_problem,
    page_fingerprint,
    page_shapes,
    page_snapshot,
    pages,
    shape_identity,
)
from odfa11y.concepts.preservation import opaque_payloads
from odfa11y.concepts.table_identity import table_content_fingerprint, table_fingerprint
from odfa11y.concepts.tables import (
    AXES,
    axis_count,
    cell_at,
    declarations,
    header_count,
    repeated,
    require_safe_boundary,
)
from odfa11y.concepts.text import eligible_text_node, reading_context_path, visible_words
from odfa11y.concepts.xml import protected_xml

__all__ = [
    "AXES",
    "CHANNEL_ATTRIBUTES",
    "SHAPE_TAGS",
    "GraphicIdentity",
    "audit_graphic_role",
    "axis_count",
    "cell_at",
    "declarations",
    "document_links",
    "effective_graphic_role",
    "eligible_text_node",
    "graphic_selector",
    "graphics_fingerprint",
    "header_count",
    "link_decision",
    "link_fingerprint",
    "link_has_description",
    "link_location",
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
