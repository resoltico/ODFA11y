# SPDX-License-Identifier: MPL-2.0
"""Offline Base declarations preserve SQL, settings and real embedded database bytes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, override

import pytest
from lxml import etree

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.audit import audit_odf
from odfa11y.config import load_config
from odfa11y.errors import ConfigError, RemediationError
from odfa11y.families.database import DatabaseDescription, SetObjectDescriptions
from odfa11y.families.database.descriptions import fingerprint, targets
from odfa11y.fidelity import FidelityPolicy
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.pipeline import PipelineOptions, run_pipeline
from odfa11y.remediation import SetMetadata, remediate

SOURCE = Path(__file__).parent / "family_corpus/fruit-database.odb"


def _query_source(tmp_path: Path, *, duplicate: bool = False) -> Path:
    document = OdfDocument.open(SOURCE)
    database = select_elements(document.edit(Part.CONTENT), "//office:database")[0]
    queries = etree.SubElement(database, qn("db", "queries"))
    for _ in range(2 if duplicate else 1):
        etree.SubElement(
            queries,
            qn("db", "query"),
            {
                qn("db", "name"): "Fruit totals",
                qn("db", "command"): 'SELECT "Item", "Count" FROM "Fruit"',
                qn("db", "escape-processing"): "true",
            },
        )
    destination = tmp_path / "queries.odb"
    document.save(destination)
    assert validate(OdfDocument.open(destination)).count == 0
    return destination


def test_real_embedded_base_validates_and_creates_optional_metadata_without_storage_changes(
    tmp_path: Path,
) -> None:
    source = OdfDocument.open(SOURCE)
    assert validate(source).count == 0
    assert not source.has(Part.META)
    destination = tmp_path / "described.odb"
    remediate(
        SOURCE,
        destination,
        [
            SetMetadata(
                title="Fruit counts",
                description="Invented local fruit counts",
                language="en-US",
            )
        ],
    )
    result = OdfDocument.open(destination)
    assert result.has(Part.META)
    assert validate(result).count == 0
    assert source.storage.read("database/firebird.fbk") == result.storage.read(
        "database/firebird.fbk"
    )
    assert source.storage.read("settings.xml") == result.storage.read("settings.xml")
    assert audit_odf(destination).passed
    twice = tmp_path / "twice.odb"
    assert not remediate(destination, twice, [SetMetadata(title="Fruit counts")]).changed
    assert destination.read_bytes() == twice.read_bytes()


def test_query_description_is_explicit_and_preserves_sql_and_bindings(tmp_path: Path) -> None:
    source = _query_source(tmp_path)
    document = OdfDocument.open(source)
    available = targets(document)
    target = "content/query[name=Fruit%20totals]"
    node = available[target][0]
    output = tmp_path / "described-query.odb"
    remediate(
        source,
        output,
        [
            SetObjectDescriptions({
                target: DatabaseDescription("Fruit names and counts", fingerprint(node)),
            })
        ],
    )
    after = targets(OdfDocument.open(output))[target][0]
    assert after.get(qn("db", "command")) == 'SELECT "Item", "Count" FROM "Fruit"'
    assert after.get(qn("db", "description")) == "Fruit names and counts"
    assert validate(OdfDocument.open(output)).count == 0


def test_duplicate_and_stale_object_targets_reject_without_any_edits(tmp_path: Path) -> None:
    document = OdfDocument.open(_query_source(tmp_path, duplicate=True))
    target = "content/query[name=Fruit%20totals]"
    result = SetObjectDescriptions({target: DatabaseDescription("Chosen meaning")}).apply(document)
    assert result[0].status is Status.FAILED
    assert document.edit_count == 0
    document = OdfDocument.open(_query_source(tmp_path))
    result = SetObjectDescriptions({target: DatabaseDescription("Chosen meaning", "stale")}).apply(
        document
    )
    assert result[0].status is Status.FAILED
    assert document.edit_count == 0


@dataclass(frozen=True, slots=True)
class ChangeQuery(Operation):
    """A negative control that changes behavior rather than describing it."""

    name: ClassVar[str] = "change_query"

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        select_elements(document.edit(Part.CONTENT), "//db:query")[0].set(
            qn("db", "command"), "DROP TABLE Fruit"
        )
        return (Outcome(self.name, Status.APPLIED, "Changed SQL", count=1),)


def test_sql_changes_are_rejected_before_output_publication(tmp_path: Path) -> None:
    source = _query_source(tmp_path)
    output = tmp_path / "bad.odb"
    with pytest.raises(RemediationError, match="content changed"):
        remediate(source, output, [ChangeQuery()])
    assert not output.exists()


def test_external_authentication_findings_do_not_disclose_values(tmp_path: Path) -> None:
    document = OdfDocument.open(SOURCE)
    resource = select_elements(document.edit(Part.CONTENT), "//db:connection-resource")[0]
    resource.set(qn("xlink", "href"), "sdbc:postgresql://alice:private-secret@example.invalid/db")
    output = tmp_path / "external.odb"
    document.save(output)
    report = audit_odf(output)
    assert {"BASE002", "BASE003"} <= {f.rule_id for f in report.findings}
    assert "private-secret" not in str(report.as_dict())
    assert "alice" not in str(report.as_dict())


def test_database_configuration_is_strict(tmp_path: Path) -> None:
    plan = tmp_path / "plan.toml"
    plan.write_text('[database.descriptions."content/query[name=Fruit]"]\ntext = "Fruit counts"\n')
    assert load_config(plan).operations == (
        SetObjectDescriptions({
            "content/query[name=Fruit]": DatabaseDescription("Fruit counts"),
        }),
    )
    plan.write_text('[database]\nconnection = "execute"\n')
    with pytest.raises(ConfigError, match="Unknown database keys"):
        load_config(plan)


def test_base_source_assurance_and_pdf_boundary_are_explicit(tmp_path: Path) -> None:
    operations = [SetMetadata(title="Fruit counts", language="en-US")]
    inspected = run_pipeline(
        SOURCE,
        operations,
        FidelityPolicy(),
        tmp_path / "inspect",
        PipelineOptions(profile="inspect"),
    )
    assert inspected.exit_status == 0
    production = run_pipeline(
        SOURCE,
        operations,
        FidelityPolicy(),
        tmp_path / "production",
        PipelineOptions(profile="production"),
    )
    assert production.exit_status != 0
    assert not (tmp_path / "production/candidate.pdf").exists()
