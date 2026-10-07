# SPDX-License-Identifier: MPL-2.0
"""Compare a candidate render with its source render."""

from .compare import compare_pdfs
from .policy import PAGINATION_MODES, FidelityPolicy

__all__ = ["PAGINATION_MODES", "FidelityPolicy", "compare_pdfs"]
