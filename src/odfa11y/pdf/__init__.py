# SPDX-License-Identifier: AGPL-3.0-only
"""PDF structural inspection, veraPDF validation and fidelity reading support."""

from odfa11y.pdf.audit import audit_pdfua
from odfa11y.pdf.structure.fonts import list_fonts
from odfa11y.pdf.validation import FailedRule, VeraPdfResult, add_verapdf_findings

__all__ = [
    "FailedRule",
    "VeraPdfResult",
    "add_verapdf_findings",
    "audit_pdfua",
    "list_fonts",
]
