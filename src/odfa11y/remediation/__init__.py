# SPDX-License-Identifier: MPL-2.0
"""Explicit, text-preserving ODT remediation as typed operations under one executor."""

from .apply import remediate
from .graphics import SetAltText
from .links import LinkifyAddresses, linkify_plain_addresses
from .metadata import SetMetadata
from .outcome import AltText, Operation, Outcome, RemediationResult, Status
from .spacers import RemoveEmptySpacers
from .spacing import NormalizeSpacing, clone_style_name
from .tables import MarkHeaderRows
from .version import SetOdfVersion

__all__ = [
    "AltText",
    "LinkifyAddresses",
    "MarkHeaderRows",
    "NormalizeSpacing",
    "Operation",
    "Outcome",
    "RemediationResult",
    "RemoveEmptySpacers",
    "SetAltText",
    "SetMetadata",
    "SetOdfVersion",
    "Status",
    "clone_style_name",
    "linkify_plain_addresses",
    "remediate",
]
