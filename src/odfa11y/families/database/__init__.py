# SPDX-License-Identifier: MPL-2.0
"""Offline assurance for standard OpenDocument database declarations."""

from .adapter import ADAPTER
from .descriptions import DatabaseDescription, SetObjectDescriptions

__all__ = ["ADAPTER", "DatabaseDescription", "SetObjectDescriptions"]
