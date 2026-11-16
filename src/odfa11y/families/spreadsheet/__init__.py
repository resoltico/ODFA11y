# SPDX-License-Identifier: AGPL-3.0-only
"""The spreadsheet family: audit rules, operations and plan tables for Calc documents."""

from odfa11y.families.spreadsheet.name_rules import invalid_name_reason
from odfa11y.families.spreadsheet.spec import SPEC

__all__ = ["SPEC", "invalid_name_reason"]
