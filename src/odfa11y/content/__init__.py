# SPDX-License-Identifier: MPL-2.0
"""Shared ODF content vocabulary, without document-family decisions."""

from .configuration import graphic_descriptions, page_decisions
from .graphics import (
    GraphicDescription,
    GraphicEditor,
    graphic_keys,
    graphics_fingerprint,
    set_description,
)
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
from .tables import (
    AXES,
    axis_count,
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
    "PageDecision",
    "PageEditor",
    "axis_count",
    "declarations",
    "graphic_descriptions",
    "graphic_keys",
    "graphics_fingerprint",
    "header_count",
    "navigation_problem",
    "opaque_payloads",
    "page_decisions",
    "page_fingerprint",
    "page_shapes",
    "page_snapshot",
    "pages",
    "protected_xml",
    "repeated",
    "require_safe_boundary",
    "set_description",
    "set_style_language",
    "shape_identity",
    "style_language",
    "table_content_fingerprint",
    "table_fingerprint",
    "visible_words",
]
