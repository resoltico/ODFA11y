# SPDX-License-Identifier: MPL-2.0
"""Shared ODF content vocabulary, without document-family decisions."""

from .graphics import GraphicDescription, GraphicEditor, frame_keys, graphics_fingerprint
from .language import set_style_language, style_language
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
from .xml import protected_xml

__all__ = [
    "AXES",
    "GraphicDescription",
    "GraphicEditor",
    "axis_count",
    "declarations",
    "frame_keys",
    "graphics_fingerprint",
    "header_count",
    "opaque_payloads",
    "protected_xml",
    "repeated",
    "require_safe_boundary",
    "set_style_language",
    "style_language",
    "table_content_fingerprint",
    "table_fingerprint",
]
