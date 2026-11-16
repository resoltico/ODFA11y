# SPDX-License-Identifier: MPL-2.0
"""Offline Base declarations preserve SQL, settings and real embedded database bytes."""

from dataclasses import dataclass
from typing import ClassVar, override
lazy from pathlib import Path

import pytest
from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.decisions.edit import Outcome, Status
from odfa11y.errors import PlanError
from odfa11y.families.database.descriptions import fingerprint, targets
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.plans.fidelity import Pagination
from odfa11y.plans.registry import load_plan
from odfa11y.rules import registry as rules
from odfa11y.status import Profile
from tests.fixtures.answers import (
    FaultEdit,
    apply_in_memory,
    database_answer,
    database_inputs,
    metadata_input,
)
from tests.fixtures.native import native_fakes
from tests.fixtures.operations import apply_answers, assert_refused
from tests.fixtures.paths import TESTS
from tests.fixtures.plans import plan_header, reviewed_plan
from tests.fixtures.runs import RunSettings, execute

SOURCE = TESTS / "corpus/families/fruit-database.odb"


def _query_source(tmp_path: Path, *, duplicate: bool = False) -> Path:
    document = OdfDocument.open(SOURCE)
    database = select_elements(document.tree(Part.CONTENT), "//office:database")[0]
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
    apply_answers(
        SOURCE,
        destination,
        [
            metadata_input(
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
    assert audit_odf(destination).error_count == 0
    twice = tmp_path / "twice.odb"
    assert not apply_answers(destination, twice, [metadata_input(title="Fruit counts")]).changed
    assert destination.read_bytes() == twice.read_bytes()


def test_query_description_is_explicit_and_preserves_sql_and_bindings(tmp_path: Path) -> None:
    source = _query_source(tmp_path)
    document = OdfDocument.open(source)
    available = targets(document)
    target = "content/query[name=Fruit%20totals]"
    node = available[target][0]
    output = tmp_path / "described-query.odb"
    apply_answers(
        source,
        output,
        [
            database_inputs({
                target: database_answer("Fruit names and counts", fingerprint(node)),
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
    with pytest.raises(PlanError, match="exactly one"):
        apply_in_memory(document, database_inputs({target: database_answer("Chosen meaning")}))
    assert not document.dirty
    document = OdfDocument.open(_query_source(tmp_path))
    with pytest.raises(PlanError, match="fingerprint"):
        apply_in_memory(
            document, database_inputs({target: database_answer("Chosen meaning", "0" * 16)})
        )
    assert not document.dirty


@dataclass(frozen=True, slots=True)
class ChangeQuery(FaultEdit):
    """A negative control that changes behavior rather than describing it."""

    name: ClassVar[str] = "change_query"

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        select_elements(document.tree(Part.CONTENT), "//db:query")[0].set(
            qn("db", "command"), "DROP TABLE Fruit"
        )
        return (Outcome(self.name, Status.APPLIED, "Changed SQL", count=1),)


def test_sql_changes_are_rejected_before_output_publication(tmp_path: Path) -> None:
    source = _query_source(tmp_path)
    output = tmp_path / "bad.odb"
    assert_refused(apply_answers(source, output, [ChangeQuery()]), match="content changed")
    assert not output.exists()


def test_external_authentication_findings_do_not_disclose_values(tmp_path: Path) -> None:
    document = OdfDocument.open(SOURCE)
    resource = select_elements(document.tree(Part.CONTENT), "//db:connection-resource")[0]
    resource.set(qn("xlink", "href"), "sdbc:postgresql://alice:private-secret@example.invalid/db")
    output = tmp_path / "external.odb"
    document.save(output)
    report = audit_odf(output)
    assert {rules.DATABASE004.id, rules.DATABASE006.id} <= {f.rule_id for f in report.findings}
    assert "private-secret" not in str(report.as_dict())
    assert "alice" not in str(report.as_dict())


def test_database_configuration_is_strict(tmp_path: Path) -> None:
    plan = tmp_path / "plan.toml"
    plan.write_text(
        plan_header(SOURCE)
        + (
            '[decisions."database.description"."content/query[name=Fruit]"]\n'
            'text = "Fruit counts"\n'
            'fingerprint = "0123456789abcdef"\n'
        )
    )
    (decision,) = load_plan(plan).decisions
    assert decision.kind.id == "database.description"
    assert decision.answer.text == "Fruit counts"
    assert decision.target is not None
    assert decision.target.fingerprint == "0123456789abcdef"
    plan.write_text(
        plan_header(SOURCE)
        + '[decisions."database.description"."content/query[1]"]\n'
        + 'connection = "execute"\nfingerprint = "0123456789abcdef"\n'
    )
    with pytest.raises(PlanError, match="Unknown"):
        load_plan(plan)


def test_base_source_assurance_and_pdf_boundary_are_explicit(tmp_path: Path) -> None:
    operations = [metadata_input(title="Fruit counts", language="en-US")]
    inspected = execute(
        SOURCE,
        reviewed_plan(SOURCE, operations, Pagination.SAME()),
        tmp_path / "source",
        RunSettings(profile=Profile.parse("source")),
        native_tools=native_fakes(),
    )
    assert inspected.exit_status == 0
    production = execute(
        SOURCE,
        reviewed_plan(SOURCE, operations, Pagination.SAME()),
        tmp_path / "production",
        RunSettings(profile=Profile.parse("production")),
        native_tools=native_fakes(),
    )
    assert production.exit_status != 0
    assert not (tmp_path / "production/candidate.pdf").exists()
