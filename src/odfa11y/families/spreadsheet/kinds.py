# SPDX-License-Identifier: AGPL-3.0-only
"""Reviewed sheet, graphic and link answer contracts."""

from odfa11y.concepts.kinds import GRAPHIC_ALTERNATIVE, LINK_DESCRIPTION
from odfa11y.decisions import DecisionKind, DecisionScope
from odfa11y.decisions.constraints import KindConstraints
from odfa11y.families.spreadsheet.answers import SheetNameAnswer
from odfa11y.families.spreadsheet.domains import SHEETS
from odfa11y.families.spreadsheet.names import edit_sheet_name, validate_renames
from odfa11y.rules import registry as rules

SHEET_NAME = DecisionKind(
    "sheet.name",
    DecisionScope.TARGET,
    SheetNameAnswer,
    domain=SHEETS,
    resolves=(rules.SHEET001, rules.SHEET002),
    edit=edit_sheet_name,
    constraints=KindConstraints(checks=(validate_renames,)),
)
DECISION_KINDS = (SHEET_NAME, GRAPHIC_ALTERNATIVE, LINK_DESCRIPTION)
