# SPDX-License-Identifier: MPL-2.0
"""Read explicit formula alternatives and their optional reviewed fingerprint."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import config_tables
from odfa11y.errors import ConfigError

from .alternative import SetFormulaAlternative

if TYPE_CHECKING:
    from odfa11y.adapter import Operation


def parse_table(data: dict[str, object]) -> list[Operation]:
    """Read one explicitly written alternative, never inferring mathematical meaning.

    Returns
    -------
    list[Operation]
        The requested alternative operation, or no operations for an empty table.

    Raises
    ------
    ConfigError
        A key/type is invalid or a fingerprint has no alternative decision.

    """
    config_tables.known(data, {"alternative", "fingerprint"}, "formula")
    values = config_tables.typed(data, str, "formula")
    if not values:
        return []
    text = values.get("alternative")
    if text is None or not text.strip():
        msg = "formula.alternative must be a nonblank spoken alternative"
        raise ConfigError(msg)
    return [SetFormulaAlternative(text, values.get("fingerprint"))]
