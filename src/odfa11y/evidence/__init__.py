# SPDX-License-Identifier: AGPL-3.0-only
"""Declared, redacted evidence artifacts and manifest integrity verification."""

from odfa11y.evidence.redact import Redactor
lazy from odfa11y.evidence.bundle import (
    BinaryArtifact,
    BundleArtifact,
    JsonArtifact,
    TextArtifact,
    XmlArtifact,
    require_free_directory,
    write_bundle,
)
lazy from odfa11y.evidence.manifest import check_bundle

__all__ = [
    "BinaryArtifact",
    "BundleArtifact",
    "JsonArtifact",
    "Redactor",
    "TextArtifact",
    "XmlArtifact",
    "check_bundle",
    "require_free_directory",
    "write_bundle",
]
