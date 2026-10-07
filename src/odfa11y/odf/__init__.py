# SPDX-License-Identifier: MPL-2.0
"""Read and edit ODF packages, XML content, styles, text and schema validity."""

from .archive import is_unsafe_member_name
from .document import OdtDocument
from .links import URI_RE, split_trailing_punctuation
from .namespaces import NS, qn
from .package import ODT_MIMETYPE, REQUIRED_XML, OdtPackage
from .prose import prose_slots
from .schema import (
    SUPPORTED_VERSIONS,
    SchemaResult,
    declared_version,
    provenance,
    regressions,
    validate,
)
from .spacers import spacer_candidates
from .styles import StyleCatalog
from .text import element_text, is_empty_paragraph, text_is_preserved, visible_text_snapshot
from .xpath import select_elements

__all__ = [
    "NS",
    "ODT_MIMETYPE",
    "REQUIRED_XML",
    "SUPPORTED_VERSIONS",
    "URI_RE",
    "OdtDocument",
    "OdtPackage",
    "SchemaResult",
    "StyleCatalog",
    "declared_version",
    "element_text",
    "is_empty_paragraph",
    "is_unsafe_member_name",
    "prose_slots",
    "provenance",
    "qn",
    "regressions",
    "select_elements",
    "spacer_candidates",
    "split_trailing_punctuation",
    "text_is_preserved",
    "validate",
    "visible_text_snapshot",
]
