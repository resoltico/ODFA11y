# SPDX-License-Identifier: MPL-2.0
"""PDF structural inspection, veraPDF validation and fidelity reading support."""

from odfa11y.pdf.audit import audit_pdfua
from odfa11y.pdf.fonts import list_fonts
from odfa11y.pdf.validation import FailedRule, VeraPdfResult, add_verapdf_findings

__all__ = [
    "FailedRule",
    "VeraPdfResult",
    "add_verapdf_findings",
    "audit_pdfua",
    "list_fonts",
]
