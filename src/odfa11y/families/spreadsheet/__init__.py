# SPDX-License-Identifier: MPL-2.0
"""The spreadsheet family: audit rules, operations and plan tables for Calc documents."""

from odfa11y.families.spreadsheet.names import SetSheetNames, invalid_name_reason
from odfa11y.families.spreadsheet.objects import SetGraphicAlternatives, SetLinkDescriptions
from odfa11y.families.spreadsheet.snapshot import sheet_snapshot, sheets_preserved
from odfa11y.families.spreadsheet.spec import ADAPTER

__all__ = [
    "ADAPTER",
    "SetGraphicAlternatives",
    "SetLinkDescriptions",
    "SetSheetNames",
    "invalid_name_reason",
    "sheet_snapshot",
    "sheets_preserved",
]
