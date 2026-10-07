# SPDX-License-Identifier: MPL-2.0
"""Independent Base controls cover nested review identity and flat settings boundaries."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, override

import pytest
from lxml import etree

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.audit import audit_odf
from odfa11y.errors import RemediationError
from odfa11y.families.database import DatabaseDescription, SetObjectDescriptions
from odfa11y.families.database.descriptions import fingerprint, targets
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.remediation import SetMetadata, remediate

CONFIG = "{urn:oasis:names:tc:opendocument:xmlns:config:1.0}"
SOURCE = Path(__file__).parent / "family_corpus/fruit-database.odb"


@dataclass(frozen=True, slots=True)
class ChangeDatabaseSettings(Operation):
    """Negative control edits a flat document's protected connection-related setting."""

    name: ClassVar[str] = "change_database_settings"

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        root = document.edit(Part.SETTINGS).getroot()
        item = next(root.iter(CONFIG + "config-item"))
        item.text = "Changed the setting"
        return (Outcome(self.name, Status.APPLIED, "Changed a setting", count=1),)


def _nested_queries(document: OdfDocument) -> None:
    database = select_elements(document.edit(Part.CONTENT), "//office:database")[0]
    queries = etree.SubElement(database, qn("db", "queries"))
    collection = etree.SubElement(
        queries, qn("db", "query-collection"), {qn("db", "name"): "Fruit"}
    )
    query = etree.SubElement(
        collection,
        qn("db", "query"),
        {qn("db", "name"): "Counts", qn("db", "command"): 'SELECT "Count" FROM "Fruit"'},
    )
    columns = etree.SubElement(query, qn("db", "columns"))
    etree.SubElement(columns, qn("db", "column"), {qn("db", "name"): "Count"})


def _descriptions(document: OdfDocument) -> SetObjectDescriptions:
    return SetObjectDescriptions({
        path: DatabaseDescription("Explicit object meaning", fingerprint(nodes[0]))
        for path, nodes in targets(document).items()
    })


def test_nested_database_descriptions_do_not_invalidate_their_own_review(tmp_path: Path) -> None:
    document = OdfDocument.open(SOURCE)
    _nested_queries(document)
    source = document.save(tmp_path / "nested.odb")
    assert validate(OdfDocument.open(source)).count == 0
    plan = _descriptions(OdfDocument.open(source))
    assert len(plan.entries) == 3
    first, second = tmp_path / "first.odb", tmp_path / "second.odb"
    assert remediate(source, first, [plan]).changed
    assert not remediate(first, second, [plan]).changed
    assert first.read_bytes() == second.read_bytes()
    assert "BASE004" not in {finding.rule_id for finding in audit_odf(second).findings}
    assert OdfDocument.open(second).storage.read("database/firebird.fbk") == document.storage.read(
        "database/firebird.fbk"
    )


def test_nested_database_sql_still_invalidates_parent_and_child_review() -> None:
    document = OdfDocument.open(SOURCE)
    _nested_queries(document)
    before = targets(document)
    fingerprints = {path: fingerprint(nodes[0]) for path, nodes in before.items()}
    query = select_elements(document.tree(Part.CONTENT), "//db:query")[0]
    query.set(qn("db", "command"), 'DELETE FROM "Fruit"')
    after = targets(document)
    collection = next(path for path in after if "/query[" not in path and "/column[" not in path)
    query_path = next(path for path in after if "/query[" in path and "/column[" not in path)
    assert fingerprint(after[collection][0]) != fingerprints[collection]
    assert fingerprint(after[query_path][0]) != fingerprints[query_path]


def test_flat_base_metadata_edits_protect_settings_without_freezing_whole_document(
    tmp_path: Path,
) -> None:
    document = OdfDocument.open(SOURCE)
    _nested_queries(document)
    root = etree.Element(
        qn("office", "document"),
        nsmap=document.tree(Part.CONTENT).getroot().nsmap,
        attrib={
            qn("office", "version"): "1.4",
            qn("office", "mimetype"): "application/vnd.oasis.opendocument.base",
        },
    )
    settings = etree.SubElement(root, qn("office", "settings"))
    setting_set = etree.SubElement(
        settings, CONFIG + "config-item-set", {CONFIG + "name": "database-properties"}
    )
    item = etree.SubElement(
        setting_set,
        CONFIG + "config-item",
        {CONFIG + "name": "OfflineReview", CONFIG + "type": "string"},
    )
    item.text = "Preserve this invented setting"
    root.append(deepcopy(select_elements(document.tree(Part.CONTENT), "//office:body")[0]))
    source = tmp_path / "flat.fodb"
    source.write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    before = OdfDocument.open(source)
    assert validate(before).count == 0
    destination = tmp_path / "described.fodb"
    plan = _descriptions(before)
    assert remediate(
        source, destination, [SetMetadata(title="Fruit database", language="en-US"), plan]
    ).changed
    after = OdfDocument.open(destination)
    before_settings = select_elements(before.tree(Part.CONTENT), "//office:settings")[0]
    after_settings = select_elements(after.tree(Part.CONTENT), "//office:settings")[0]
    assert etree.tostring(before_settings, method="c14n", exclusive=True) == etree.tostring(
        after_settings, method="c14n", exclusive=True
    )
    assert not remediate(destination, tmp_path / "again.fodb", [plan]).changed
    wrong = tmp_path / "wrong.fodb"
    with pytest.raises(RemediationError, match="content changed"):
        remediate(destination, wrong, [ChangeDatabaseSettings()])
    assert not wrong.exists()
