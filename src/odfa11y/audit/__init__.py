# SPDX-License-Identifier: MPL-2.0
"""Read-only ODF accessibility audit and configuration templates."""

from .engine import BLOCKING_RULE_IDS, audit_odf
from .template import render_template

__all__ = ["BLOCKING_RULE_IDS", "audit_odf", "render_template"]
