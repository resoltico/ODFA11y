# SPDX-License-Identifier: MPL-2.0
"""The spreadsheet family: audit rules, operations and plan tables for Calc documents."""

from .adapter import ADAPTER
from .names import SetSheetNames, invalid_name_reason
from .objects import SetGraphicDescriptions
from .snapshot import sheet_snapshot, sheets_preserved

__all__ = [
    "ADAPTER",
    "SetGraphicDescriptions",
    "SetSheetNames",
    "invalid_name_reason",
    "sheet_snapshot",
    "sheets_preserved",
]
