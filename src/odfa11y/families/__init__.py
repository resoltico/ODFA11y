# SPDX-License-Identifier: MPL-2.0
"""Explicit supported document-family records."""

from odfa11y.families.catalogue import REGISTRY, require_spec, spec_for
from odfa11y.families.spec import FamilySpec, LanguageTargets, PdfExport, Unsupported

__all__ = [
    "REGISTRY",
    "FamilySpec",
    "LanguageTargets",
    "PdfExport",
    "Unsupported",
    "require_spec",
    "spec_for",
]
