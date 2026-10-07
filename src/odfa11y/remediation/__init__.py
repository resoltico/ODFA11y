# SPDX-License-Identifier: MPL-2.0
"""Explicit ODT remediation and spacing normalization."""

from .config import load_remediation_config, validate_alt_text
from .links import linkify_plain_addresses
from .models import AltText, RemediationOptions, RemediationResult
from .odt import remediate_odt
from .spacing import normalize_paragraph_spacing

__all__ = [
    "AltText",
    "RemediationOptions",
    "RemediationResult",
    "linkify_plain_addresses",
    "load_remediation_config",
    "normalize_paragraph_spacing",
    "remediate_odt",
    "validate_alt_text",
]
