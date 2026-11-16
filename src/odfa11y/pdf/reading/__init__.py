# SPDX-License-Identifier: MPL-2.0
"""The bounded acquisition boundary shared by every PDF consumer."""

from odfa11y.pdf.reading.limits import Limits, default_limits
from odfa11y.pdf.reading.reader import BoundedPdf, open_pdf

__all__ = ["BoundedPdf", "Limits", "default_limits", "open_pdf"]
