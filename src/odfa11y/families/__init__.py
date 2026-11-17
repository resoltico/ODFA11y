# SPDX-License-Identifier: AGPL-3.0-only
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
