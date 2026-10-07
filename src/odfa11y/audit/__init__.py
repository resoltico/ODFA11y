# SPDX-License-Identifier: MPL-2.0
"""Read-only ODT accessibility audit and configuration templates."""

from .odt import audit_odt
from .template import render_template

__all__ = ["audit_odt", "render_template"]
