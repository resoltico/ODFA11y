# SPDX-License-Identifier: MPL-2.0
"""Reviewed sheet, graphic and link answer contracts."""

from odfa11y.concepts.kinds import GRAPHIC_ALTERNATIVE, LINK_DESCRIPTION
from odfa11y.decisions import DecisionKind, DecisionScope
from odfa11y.families.spreadsheet.answers import SheetNameAnswer
from odfa11y.families.spreadsheet.domains import SHEETS
from odfa11y.families.spreadsheet.names import edit_sheet_name
from odfa11y.rules import registry as rules

SHEET_NAME = DecisionKind(
    "sheet.name",
    DecisionScope.TARGET,
    SheetNameAnswer,
    domain=SHEETS,
    resolves=(rules.SHEET001, rules.SHEET002),
    edit=edit_sheet_name,
)
DECISION_KINDS = (SHEET_NAME, GRAPHIC_ALTERNATIVE, LINK_DESCRIPTION)
