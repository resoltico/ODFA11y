# SPDX-License-Identifier: MPL-2.0
"""PDF structural inspection, veraPDF validation and fidelity reading support."""

from odfa11y.pdf.audit import audit_pdfua
from odfa11y.pdf.fonts import list_fonts
from odfa11y.pdf.validate import (
    FailedRule,
    VeraPdfResult,
    add_verapdf_findings,
    check_pdfua,
    find_verapdf,
    validate_pdfua,
)

__all__ = [
    "FailedRule",
    "VeraPdfResult",
    "add_verapdf_findings",
    "audit_pdfua",
    "check_pdfua",
    "find_verapdf",
    "list_fonts",
    "validate_pdfua",
]
