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


def test_standard_server_database_declaration_is_external_instead_of_missing(
    tmp_path: Path,
) -> None:
    document = OdfDocument.open(SOURCE)
    connection = select_elements(document.edit(Part.CONTENT), "//db:connection-data")[0]
    resource = select_elements(connection, "./db:connection-resource")[0]
    connection.remove(resource)
    description = etree.Element(qn("db", "database-description"))
    etree.SubElement(
        description,
        qn("db", "server-database"),
        {
            qn("db", "type"): "db:postgresql",
            qn("db", "hostname"): "invalid.example",
            qn("db", "port"): "5432",
            qn("db", "database-name"): "private-invented-database",
        },
    )
    connection.insert(0, description)
    source = document.save(tmp_path / "server.odb")
    assert validate(OdfDocument.open(source)).count == 0
    report = audit_odf(source)
    assert "BASE002" in {finding.rule_id for finding in report.findings}
    assert "BASE001" not in {finding.rule_id for finding in report.findings}
    assert report.metadata["connection_declarations"] == 1
    assert "invalid.example" not in str(report.as_dict())
    assert "private-invented-database" not in str(report.as_dict())


@pytest.mark.parametrize("part", ["content", "settings", "flat"])
@pytest.mark.parametrize(
    "case",
    [
        ("Password", "string", "invented-sensitive-value", True),
        ("User_Name", "string", "invented-sensitive-value", True),
        ("Auth", "string", "invented-sensitive-value", True),
        ("Access-Token", "string", "invented-sensitive-value", True),
        ("ClientSecret", "string", "invented-sensitive-value", True),
        ("API Key", "string", "invented-sensitive-value", True),
        ("PasswordRequired", "boolean", "true", False),
        ("UsePassword", "boolean", "true", False),
        ("Password", "boolean", "false", False),
        ("AuthMode", "string", "OAuth", False),
        ("Password", "string", "  ", False),
    ],
)
def test_named_authentication_settings_are_reported_without_exposing_values(
    tmp_path: Path, part: str, case: tuple[str, str, str, bool]
) -> None:
    name, kind, value, credential = case
    document = OdfDocument.open(SOURCE)
    if part == "content":
        application = select_elements(
            document.edit(Part.CONTENT), "//db:application-connection-settings"
        )[0]
        settings = etree.SubElement(application, qn("db", "data-source-settings"))
        setting = etree.SubElement(
            settings,
            qn("db", "data-source-setting"),
            {
                qn("db", "data-source-setting-name"): name,
                qn("db", "data-source-setting-type"): kind,
            },
        )
        etree.SubElement(setting, qn("db", "data-source-setting-value")).text = value
    else:
        settings = etree.SubElement(
            document.edit(Part.SETTINGS).getroot(), qn("office", "settings")
        )
        setting_set = etree.SubElement(
            settings, CONFIG + "config-item-set", {CONFIG + "name": "Database"}
        )
        etree.SubElement(
            setting_set, CONFIG + "config-item", {CONFIG + "name": name, CONFIG + "type": kind}
        ).text = value
    if part == "flat":
        root = deepcopy(document.tree(Part.CONTENT).getroot())
        root.tag = qn("office", "document")
        root.set(qn("office", "mimetype"), "application/vnd.oasis.opendocument.base")
        root.insert(0, deepcopy(settings))
        source = tmp_path / "settings.fodb"
        source.write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    else:
        source = document.save(tmp_path / "settings.odb")
    assert validate(OdfDocument.open(source)).count == 0
    report = audit_odf(source)
    assert ("BASE003" in {finding.rule_id for finding in report.findings}) is credential
    assert sum(finding.rule_id == "BASE003" for finding in report.findings) <= 1
    assert "invented-sensitive-value" not in str(report.as_dict())
