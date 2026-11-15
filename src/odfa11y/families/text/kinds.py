# SPDX-License-Identifier: MPL-2.0
"""Writer answer contracts and translation into preservation-guarded operations."""

from odfa11y.concepts.kinds import GRAPHIC_ALTERNATIVE, LINK_DESCRIPTION
from odfa11y.decisions import DecisionKind, DecisionScope
from odfa11y.decisions.answers import SwitchAnswer
from odfa11y.families.text.answers import (
    HeadingLevelAnswer,
    TableHeadersAnswer,
    TargetLanguageAnswer,
    TextSpacingAnswer,
)
from odfa11y.families.text.domains import HEADINGS, LANGUAGES, TABLES
from odfa11y.families.text.headings.edit import edit_heading
from odfa11y.families.text.language.operations import edit_language
from odfa11y.families.text.links.edit import edit_addresses
from odfa11y.families.text.spacing.edit import edit_spacing
from odfa11y.families.text.spacing.remove import edit_spacers
from odfa11y.families.text.tables.operations import edit_headers
from odfa11y.rules import registry as rules

LINKIFY_ADDRESSES = DecisionKind(
    "text.linkify_addresses",
    DecisionScope.DOCUMENT,
    SwitchAnswer,
    resolves=(rules.LINK001,),
    edit=edit_addresses,
)
REMOVE_SPACERS = DecisionKind(
    "text.remove_spacers",
    DecisionScope.DOCUMENT,
    SwitchAnswer,
    resolves=(rules.LAYOUT001,),
    edit=edit_spacers,
)
HEADING_LEVEL = DecisionKind(
    "heading.level",
    DecisionScope.TARGET,
    HeadingLevelAnswer,
    domain=HEADINGS,
    resolves=(
        rules.HEADING001,
        rules.HEADING002,
    ),
    edit=edit_heading,
)
TABLE_HEADERS = DecisionKind(
    "table.headers",
    DecisionScope.TARGET,
    TableHeadersAnswer,
    domain=TABLES,
    resolves=(rules.TABLE003,),
    edit=edit_headers,
)
TEXT_SPACING = DecisionKind(
    "text.spacing", DecisionScope.DOCUMENT, TextSpacingAnswer, edit=edit_spacing
)
TARGET_LANGUAGE = DecisionKind(
    "language.target",
    DecisionScope.TARGET,
    TargetLanguageAnswer,
    domain=LANGUAGES,
    resolves=(rules.LANG004,),
    edit=edit_language,
)
DECISION_KINDS = (
    LINKIFY_ADDRESSES,
    REMOVE_SPACERS,
    GRAPHIC_ALTERNATIVE,
    HEADING_LEVEL,
    TABLE_HEADERS,
    TEXT_SPACING,
    LINK_DESCRIPTION,
    TARGET_LANGUAGE,
)
