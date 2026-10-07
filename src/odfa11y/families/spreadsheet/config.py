# SPDX-License-Identifier: MPL-2.0
"""Read the ``[spreadsheet]`` table of a configuration into spreadsheet operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from odfa11y.adapter import config_tables
from odfa11y.content import GraphicDescription
from odfa11y.errors import ConfigError

from .names import SetSheetNames, invalid_name_reason
from .objects import SetGraphicDescriptions

if TYPE_CHECKING:
    from odfa11y.adapter import Operation

SPREADSHEET_KEYS = {"sheet_names", "graphics"}


def parse_spreadsheet_table(data: dict[str, object]) -> list[Operation]:
    """Turn the ``[spreadsheet]`` table into operations in canonical order.

    Returns
    -------
    list[Operation]
        Sheet names, then alt text.

    """
    config_tables.known(data, SPREADSHEET_KEYS, "spreadsheet")
    operations: list[Operation] = []
    operations += _sheet_names(config_tables.table(data, "sheet_names"))
    operations += _alt_text(config_tables.table(data, "graphics"))
    return operations


def _sheet_names(table: dict[str, object]) -> list[Operation]:
    entries = config_tables.typed(table, str, "spreadsheet.sheet_names")
    for old, new in entries.items():
        if not old.strip():
            msg = "spreadsheet.sheet_names keys must name an existing sheet"
            raise ConfigError(msg)
        reason = invalid_name_reason(new)
        if reason:
            msg = f"spreadsheet.sheet_names.{old} is not a usable sheet name: {reason}"
            raise ConfigError(msg)
    return [SetSheetNames(entries)] if entries else []


def _alt_text(table: dict[str, object]) -> list[Operation]:
    entries: dict[str, GraphicDescription] = {}
    for key in table:
        entry = config_tables.table(table, key)
        label = f"spreadsheet.graphics.{key}"
        config_tables.known(entry, {"title", "description", "fingerprint"}, label)
        texts = config_tables.typed(entry, str, label)
        entries[key] = GraphicDescription(
            texts.get("title"), texts.get("description"), texts.get("fingerprint")
        )
    return [SetGraphicDescriptions(entries)] if entries else []
