# SPDX-License-Identifier: MPL-2.0
"""Read the shared, explicit graphic and page decision structures."""

from __future__ import annotations

from odfa11y.adapter import config_tables
from odfa11y.errors import ConfigError

from .graphics import GraphicDescription
from .pages import PageDecision


def graphic_descriptions(table: dict[str, object], label: str) -> dict[str, GraphicDescription]:
    """Read description entries without choosing their family applicability.

    Returns
    -------
    dict[str, GraphicDescription]
        Explicit fields and optional reviewed fingerprints.

    """
    entries = {}
    for key in table:
        value = config_tables.table(table, key)
        entry_label = f"{label}.{key}"
        config_tables.known(value, {"title", "description", "fingerprint"}, entry_label)
        texts = config_tables.typed(value, str, entry_label)
        entries[key] = GraphicDescription(
            texts.get("title"), texts.get("description"), texts.get("fingerprint")
        )
    return entries


def page_decisions(table: dict[str, object], label: str) -> dict[str, PageDecision]:
    """Read description fields and an explicitly selected complete navigation order.

    Returns
    -------
    dict[str, PageDecision]
        Per-page decisions; target/order integrity is proved against the document.

    Raises
    ------
    ConfigError
        A key/type is invalid or navigation is not a list of nonblank identity strings.

    """
    entries = {}
    for key in table:
        value = config_tables.table(table, key)
        entry_label = f"{label}.{key}"
        config_tables.known(
            value, {"title", "description", "navigation", "fingerprint"}, entry_label
        )
        texts = config_tables.typed(
            {name: text for name, text in value.items() if name != "navigation"}, str, entry_label
        )
        order = value.get("navigation")
        if order is not None and (
            not isinstance(order, list)
            or not all(isinstance(identity, str) and identity.strip() for identity in order)
        ):
            msg = f"{entry_label}.navigation must be a list of nonblank shape identities"
            raise ConfigError(msg)
        entries[key] = PageDecision(
            texts.get("title"),
            texts.get("description"),
            tuple(order) if isinstance(order, list) else None,
            texts.get("fingerprint"),
        )
    return entries
