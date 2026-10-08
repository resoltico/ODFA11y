# SPDX-License-Identifier: MPL-2.0
"""Bounded token scanning shared by PDF consumption and accessibility inspection."""

from .scan import ContentScan, scan_content

__all__ = ["ContentScan", "scan_content"]
