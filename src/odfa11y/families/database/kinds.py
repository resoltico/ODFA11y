# SPDX-License-Identifier: AGPL-3.0-only
"""Reviewed database-object description answers and operation translation."""

from odfa11y.decisions import DecisionKind, DecisionScope
from odfa11y.decisions.answers import DatabaseDescriptionAnswer
from odfa11y.families.database.descriptions import edit_description
from odfa11y.families.database.domain import OBJECTS
from odfa11y.rules import registry as rules

DATABASE_DESCRIPTION = DecisionKind(
    "database.description",
    DecisionScope.TARGET,
    DatabaseDescriptionAnswer,
    domain=OBJECTS,
    resolves=(rules.DATABASE009,),
    edit=edit_description,
)
DECISION_KINDS = (DATABASE_DESCRIPTION,)
