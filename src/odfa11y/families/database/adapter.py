# SPDX-License-Identifier: MPL-2.0
"""Database declarations and opaque storage remain offline and unchanged."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from odfa11y.adapter import FamilyAdapter, ReviewItem, config_tables
from odfa11y.content import protected_xml
from odfa11y.errors import ConfigError
from odfa11y.odf import Family, Part, qn, select_elements

from .audit import audit_database
from .descriptions import DatabaseDescription, SetObjectDescriptions, description_attributes

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from odfa11y.adapter import Operation
    from odfa11y.odf import OdfDocument
    from odfa11y.report import Finding


def _parse(data: dict[str, object]) -> list[Operation]:
    config_tables.known(data, {"descriptions"}, "database")
    entries = {}
    for target, raw in config_tables.table(data, "descriptions").items():
        if not isinstance(raw, dict):
            msg = "database.descriptions entries must be tables"
            raise ConfigError(msg)
        config_tables.known(raw, {"text", "fingerprint"}, "database description")
        values = config_tables.typed(raw, str, "database description")
        if not values.get("text", "").strip():
            msg = "database descriptions require nonblank text"
            raise ConfigError(msg)
        entries[target] = DatabaseDescription(values["text"], values.get("fingerprint"))
    return [SetObjectDescriptions(entries)] if entries else []


def _snapshot(document: OdfDocument) -> tuple[str, ...]:
    bodies = select_elements(document.tree(Part.CONTENT), "//office:body")
    facts = [
        protected_xml(body, omitted_element_attributes=description_attributes(body))
        for body in bodies
    ]
    if document.has(Part.SETTINGS):
        tree = document.tree(Part.SETTINGS)
        settings = select_elements(tree, "//office:settings")
        if document.layout == "package":
            settings = [tree.getroot()]
        facts.extend(
            protected_xml(node, omitted_root_attributes=(qn("office", "version"),))
            for node in settings
        )
    return tuple(facts)


def _preserved(before: tuple[str, ...], after: tuple[str, ...], removed: int) -> bool:
    return removed == 0 and before == after


def _language(document: OdfDocument) -> str | None:
    del document
    return None


def _set_language(document: OdfDocument, tag: str) -> bool:
    del document, tag
    return False


def _template(findings: Mapping[str, Sequence[Finding]]) -> list[str]:
    lines = []
    for finding in findings.get("database.descriptions", ()):
        target = finding.details.get("target")
        if target:
            lines += [
                f"# [database.descriptions.{json.dumps(target)}]",
                '# text = ""  # explain the declared object in context',
                f"# fingerprint = {json.dumps(finding.details.get('fingerprint', ''))}",
                "",
            ]
    return lines


ADAPTER = FamilyAdapter(
    name="database",
    family=Family.DATABASE,
    audit=audit_database,
    default_language=_language,
    set_default_language=_set_language,
    snapshot=_snapshot,
    preserved=_preserved,
    config_tables={"database": _parse},
    template=_template,
    review_items=(
        ReviewItem(
            "database meaning",
            "Whether object descriptions explain queries, tables, forms and reports.",
        ),
        ReviewItem(
            "privacy and execution",
            "Review credentials, bindings, SQL and macros offline before trusted native use.",
        ),
        ReviewItem(
            "source boundary",
            "Storage stays opaque; connections and PDF export are unsupported.",
        ),
    ),
)
