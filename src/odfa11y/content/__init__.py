# SPDX-License-Identifier: MPL-2.0
"""Shared ODF content vocabulary, without document-family decisions."""

from .configuration import graphic_descriptions, page_decisions
from .export_context import native_export_limitations, require_native_context
from .graphic_identity import GraphicIdentity, graphic_keys, graphics_fingerprint
from .graphics import GraphicDescription, GraphicEditor, set_description
from .language import set_style_language, style_language
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
from .tables import (
    AXES,
    axis_count,
    cell_at,
    declarations,
    header_count,
    repeated,
    require_safe_boundary,
    table_content_fingerprint,
    table_fingerprint,
)
from .text import visible_words
from .xml import protected_xml

__all__ = [
    "AXES",
    "SHAPE_TAGS",
    "GraphicDescription",
    "GraphicEditor",
    "GraphicIdentity",
    "PageDecision",
    "PageEditor",
    "axis_count",
    "cell_at",
    "declarations",
    "graphic_descriptions",
    "graphic_keys",
    "graphics_fingerprint",
    "header_count",
    "local_resource_path",
    "native_export_limitations",
    "navigation_problem",
    "opaque_payloads",
    "page_decisions",
    "page_fingerprint",
    "page_shapes",
    "page_snapshot",
    "pages",
    "protected_xml",
    "repeated",
    "require_native_context",
    "require_safe_boundary",
    "set_description",
    "set_style_language",
    "shape_identity",
    "style_language",
    "table_content_fingerprint",
    "table_fingerprint",
    "visible_words",
]
