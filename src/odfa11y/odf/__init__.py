# SPDX-License-Identifier: MPL-2.0
"""Read and edit ODF documents: storage, parts, kinds, detection, XML and schema validity."""

from odfa11y.odf.access import Use
from odfa11y.odf.archive import is_unsafe_member_name
from odfa11y.odf.body import body_text_snapshot
from odfa11y.odf.detect import Detection, declared_version, detect
from odfa11y.odf.document import DocumentCheckpoint, OdfDocument
from odfa11y.odf.flat import FLAT_MEMBER, FlatXmlStorage
from odfa11y.odf.kinds import KINDS, DocumentKind, Family, kind_for_media_type
from odfa11y.odf.metadata_part import ensure_metadata_part
from odfa11y.odf.names import NS, is_office_element, qn
from odfa11y.odf.opening import open_storage
from odfa11y.odf.package import PackageStorage
from odfa11y.odf.schema import (
    SUPPORTED_VERSIONS,
    SchemaResult,
    Violation,
    provenance,
    regressions,
    validate,
)
from odfa11y.odf.storage import OdfStorage, Part
from odfa11y.odf.xpath import select_elements

__all__ = [
    "FLAT_MEMBER",
    "KINDS",
    "NS",
    "SUPPORTED_VERSIONS",
    "Detection",
    "DocumentCheckpoint",
    "DocumentKind",
    "Family",
    "FlatXmlStorage",
    "OdfDocument",
    "OdfStorage",
    "PackageStorage",
    "Part",
    "SchemaResult",
    "Use",
    "Violation",
    "body_text_snapshot",
    "declared_version",
    "detect",
    "ensure_metadata_part",
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
