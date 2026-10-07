# SPDX-License-Identifier: MPL-2.0
"""Read and edit ODF documents: storage, parts, kinds, detection, XML and schema validity."""

from .archive import is_unsafe_member_name
from .body import body_text_snapshot
from .detect import Detection, declared_version, detect
from .document import OdfDocument
from .flat import FLAT_MEMBER, FlatXmlStorage
from .kinds import KINDS, DocumentKind, Family, kind_for_media_type
from .namespaces import NS, is_office_element, qn
from .opening import open_storage
from .package import PackageStorage
from .schema import (
    SUPPORTED_VERSIONS,
    SchemaResult,
    Violation,
    provenance,
    regressions,
    validate,
)
from .storage import OdfStorage, Part
from .xpath import select_elements

__all__ = [
    "FLAT_MEMBER",
    "KINDS",
    "NS",
    "SUPPORTED_VERSIONS",
    "Detection",
    "DocumentKind",
    "Family",
    "FlatXmlStorage",
    "OdfDocument",
    "OdfStorage",
    "PackageStorage",
    "Part",
    "SchemaResult",
    "Violation",
    "body_text_snapshot",
    "declared_version",
    "detect",
    "is_office_element",
    "is_unsafe_member_name",
    "kind_for_media_type",
    "open_storage",
    "provenance",
    "qn",
    "regressions",
    "select_elements",
    "validate",
]
