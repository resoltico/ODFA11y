# SPDX-License-Identifier: AGPL-3.0-only
"""Every family uses real source-bound questions, guarded publication and explicit rebinding."""

import hashlib
import tomllib
from copy import deepcopy
lazy from pathlib import Path

import pytest
from lxml import etree

from odfa11y.application.remediate import remediate
from odfa11y.audit import audit_odf, prepare_plan
from odfa11y.decisions import Decision, decode_answer
from odfa11y.errors import PackageError, PlanError
from odfa11y.odf import NS, OdfDocument, PackageStorage, Part, qn
from odfa11y.plans import Plan, parse_tables
from odfa11y.remediate.catalogue import registered_kinds
from odfa11y.report import Location
from odfa11y.rules import registry as rules
from odfa11y.targets import Fingerprint, Target, TargetPath, require_target
from tests.fixtures.paths import TESTS
from tests.fixtures.spreadsheets import make_spreadsheet, picture, row, sheet, text_cell
from tests.fixtures.writer import make_minimal_odt

FAMILY_CORPUS = TESTS / "corpus/families"
FAMILY_FIXTURES = [
    "text",
    "spreadsheet",
    "fruit-presentation.odp",
    "fruit-drawing.odg",
    "fruit-image.odi",
    "fruit-chart.odc",
    "fruit-database.odb",
    "sum-formula.odf",
]


@pytest.mark.parametrize("fixture", FAMILY_FIXTURES)
def test_family_question_roundtrip_preservation_and_rebinding(tmp_path: Path, fixture: str) -> None:
    source = family_source(tmp_path, fixture)
    document = OdfDocument.open(source)
    original_bytes = source.read_bytes()
    before = _xml_outside_document_title(document)
    plan = reviewed_title_plan(source)
    destination = tmp_path / ("reviewed" + source.suffix)
    result = remediate(source, destination, plan)
    assert result.published, result.as_dict()
    assert result.changed
    assert result.exit_status == 0
    assert rules.META001.id not in {f.rule_id for f in audit_odf(destination).findings}
    after = OdfDocument.open(destination)
    assert _xml_outside_document_title(after) == before
    assert source.read_bytes() == original_bytes
    second = tmp_path / ("second" + source.suffix)
    with pytest.raises(PlanError, match="digest mismatch"):
        remediate(destination, second, plan)
    assert not second.exists()
    reapplied = remediate(destination, second, rebound_plan(destination, plan))
    assert reapplied.published
    assert not reapplied.changed
    assert not reapplied.violations
    # A source binding never authorizes a decision belonging to another family.
    foreign = registered_kinds()["formula.alternative" if fixture == "text" else "heading.level"]
    target = None if foreign.scope == "document" else Location("content/heading[1]")
    decision = Decision(
        foreign,
        (
            None
            if target is None
            else Target(
                TargetPath((target).path), Fingerprint(None if target is None else "0" * 16)
            )
        ),
        decode_answer(
            foreign.answer_type,
            {"level": 2} if foreign.id == "heading.level" else {"alternative": "A formula"},
            foreign.id,
        ),
    )
    invalid = Plan(Plan.for_source(source).header, (decision,))
    with pytest.raises(PlanError, match="does not apply"):
        remediate(source, tmp_path / "foreign", invalid)
    assert not (tmp_path / "foreign").exists()


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("failing_target", [False, True])
def test_preview_and_publication_return_all_outcomes(
    tmp_path: Path, *, dry_run: bool, failing_target: bool
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    before = source.read_bytes()
    kinds = registered_kinds()
    metadata = kinds["document.metadata"]
    graphic = kinds["graphic.alternative"]
    decisions = [
        Decision(
            metadata, None, decode_answer(metadata.answer_type, {"title": "Reviewed"}, metadata.id)
        )
    ]
    if failing_target:
        decisions.append(
            Decision(
                graphic,
                Target(
                    TargetPath((Location("content/frame[name=Missing]")).path),
                    Fingerprint("0" * 16),
                ),
                decode_answer(graphic.answer_type, {"title": "Missing"}, graphic.id),
            )
        )
    plan = Plan.for_source(source, decisions)
    destination = tmp_path / "out.odt"
    if failing_target:
        with pytest.raises(PlanError, match="exactly one"):
            remediate(source, destination, plan, dry_run=dry_run)
        assert source.read_bytes() == before
        assert not destination.exists()
        return
    result = remediate(source, destination, plan, dry_run=dry_run)
    assert result.published is not dry_run
    assert result.exit_status == 0
    assert destination.exists() is result.published
    assert source.read_bytes() == before
    assert len(result.outcomes) == 1
    assert result.outcomes[0].status == "applied"
    assert not result.violations
    result.as_dict()


def test_sheet_and_graphic_questions_compose_and_rebind(tmp_path: Path) -> None:
    source = make_spreadsheet(tmp_path, "package", sheet("Sheet1", row(picture("Logo"))))
    report = audit_odf(source)
    decisions = []
    for question in report.decisions:
        if question.kind.id not in {"sheet.name", "graphic.alternative"}:
            continue
        values = (
            {"name": "Fruit budget"}
            if question.kind.id == "sheet.name"
            else {"title": "Fruit company"}
        )
        decisions.append(
            Decision(
                question.kind,
                require_target(question.target),
                decode_answer(question.kind.answer_type, values, question.kind.id),
            )
        )
    assert len(decisions) == 2
    plan = Plan.for_source(source, decisions)
    plan = parse_tables(plan.as_dict(), registered_kinds())
    first, second = tmp_path / "first.ods", tmp_path / "second.ods"
    result = remediate(source, first, plan)
    assert result.published, result.as_dict()
    assert not {rules.SHEET002.id, rules.GRAPHIC001.id} & {
        f.rule_id for f in audit_odf(first).findings
    }
    result = remediate(first, second, rebound_plan(first, plan))
    assert result.published, result.as_dict()
    assert not result.changed


def reviewed_title_plan(source: Path) -> Plan:
    """Enable one reviewed title in the real audit-generated plan.

    Returns
    -------
    Plan
        The bound plan with one explicit document metadata answer.

    """
    original_bytes = source.read_bytes()
    report, template = prepare_plan(source)
    assert source.read_bytes() == original_bytes
    assert template is not None
    assert any(f.rule_id == rules.META001.id for f in report.findings)
    question = next(d for d in report.decisions if d.kind.id == "document.metadata")
    # Enable only the reviewed table printed by the real plan renderer.
    preceding, marker, following = template.partition('[decisions."document.metadata"]')
    assert marker
    reviewed = (
        preceding
        + '[decisions."document.metadata"]'
        + following.replace('# title = ""', 'title = "Reviewed fruit document"', 1)
    )
    values = tomllib.loads(reviewed)
    plan = parse_tables(values, registered_kinds())
    assert plan.header.source.sha256 == hashlib.sha256(original_bytes).hexdigest()
    assert plan.decisions == (
        Decision(
            question.kind,
            None,
            decode_answer(
                question.kind.answer_type, {"title": "Reviewed fruit document"}, question.kind.id
            ),
        ),
    )
    return plan


def family_source(tmp_path: Path, fixture: str) -> Path:
    """Prepare one family source with a missing title.

    Returns
    -------
    Path
        An isolated fixture retaining the family's original body and resources.

    """
    if fixture == "text":
        original = make_minimal_odt(tmp_path / "original.odt")
    elif fixture == "spreadsheet":
        original = make_spreadsheet(tmp_path, "package", sheet("Budget", row(text_cell("Fruit"))))
    else:
        original = FAMILY_CORPUS / fixture
    document = OdfDocument.open(original)
    if document.has(Part.META):
        for title in document.tree(Part.META).findall("office:meta/dc:title", NS):
            title.text = ""
    return document.save(tmp_path / ("source" + original.suffix))


@pytest.mark.parametrize("fixture", FAMILY_FIXTURES)
@pytest.mark.parametrize("dry_run", [False, True])
def test_bound_plan_refuses_signed_packages_for_every_family(
    tmp_path: Path, fixture: str, *, dry_run: bool
) -> None:
    source = family_source(tmp_path, fixture)
    storage = PackageStorage(source)
    storage.write_member("META-INF/documentsignatures.xml", b"")
    storage.save(source)
    before = source.read_bytes()
    plan = Plan.for_source(source)
    destination = tmp_path / ("refused" + source.suffix)
    with pytest.raises(PackageError, match="Protected"):
        remediate(source, destination, plan, dry_run=dry_run)
    assert source.read_bytes() == before
    assert not destination.exists()


@pytest.mark.parametrize("fixture", FAMILY_FIXTURES)
def test_every_family_audit_preserves_live_trees_and_serializes_against_its_schema(
    tmp_path: Path, fixture: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = family_source(tmp_path, fixture)
    before_bytes = source.read_bytes()
    document = OdfDocument.open(source)
    before = document.checkpoint()
    with monkeypatch.context() as patch:
        patch.setattr(OdfDocument, "open", lambda _source: document)
        report = audit_odf(source, schema=True)
    assert not document.changed_since(before)
    assert source.read_bytes() == before_bytes
    report.as_dict()


def rebound_plan(source: Path, previous: Plan) -> Plan:
    """Exercise the new-plan workflow before applying preserved answers again."""
    _, template = prepare_plan(source, previous=previous)
    assert template is not None
    return parse_tables(tomllib.loads(template), registered_kinds())


def _xml_outside_document_title(document: OdfDocument) -> tuple[bytes, ...]:
    parts = []
    for tree in document.distinct_trees(*Part):
        root = deepcopy(tree.getroot())
        for meta in root.findall("office:meta", NS):
            for title in meta.findall("dc:title", NS):
                meta.remove(title)
            if not len(meta) and not meta.attrib:
                root.remove(meta)
        # Authoring a title may create the optional standard metadata part and entry.
        if root.tag == qn("office", "document-meta") and not len(root):
            assert set(root.attrib) <= {qn("office", "version")}
            continue
        for entry in root.findall("manifest:file-entry", NS):
            if dict(entry.attrib) == {
                qn("manifest", "full-path"): "meta.xml",
                qn("manifest", "media-type"): "text/xml",
            }:
                root.remove(entry)
        parts.append(etree.tostring(root, method="c14n", exclusive=True))
    return tuple(parts)
