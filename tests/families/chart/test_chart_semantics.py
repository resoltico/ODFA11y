# SPDX-License-Identifier: MPL-2.0
"""Native chart metadata edits preserve its data, references and source-only boundary."""

from dataclasses import dataclass
from typing import ClassVar, override
lazy from pathlib import Path

import pytest
from lxml import etree

from odfa11y.audit import audit_odf
from odfa11y.concepts.metadata import read_metadata
from odfa11y.decisions.edit import Outcome, Status
from odfa11y.errors import DocumentRefusal, PlanError
from odfa11y.families.chart.audit import ChartMeasurements, audit_chart
from odfa11y.families.chart.ranges import range_shape
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.plans.fidelity import Pagination
from odfa11y.plans.registry import load_plan
from odfa11y.report import Report, ReportKind
from odfa11y.rules import registry as rules
from odfa11y.run.context import RunSettings
from odfa11y.run.engine import execute
from odfa11y.run.profiles import profile_named
from tests.fixtures.answers import Authored, FaultEdit, metadata_input
from tests.fixtures.measurements import measurement
from tests.fixtures.operations import apply_answers, assert_refused
from tests.fixtures.paths import TESTS
from tests.fixtures.plans import reviewed_plan

SOURCE = TESTS / "family_corpus/fruit-chart.odc"


def _plan() -> list[Authored]:
    return [
        metadata_input(
            title="Fruit counts", description="Three apples and four pears", language="en-US"
        )
    ]


@dataclass(frozen=True, slots=True)
class ChangeChartData(FaultEdit):
    """Negative control changes a numerical value without changing its display string."""

    name: ClassVar[str] = "change_chart_data"

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        cell = select_elements(document.tree(Part.CONTENT), "//table:table-cell[@office:value]")[0]
        cell.set(qn("office", "value"), "999")
        return (Outcome(self.name, Status.APPLIED, "Changed data", count=1),)


def test_chart_native_source_and_metadata_preserve_all_chart_xml(tmp_path: Path) -> None:
    before = OdfDocument.open(SOURCE)
    assert validate(before).count == 0
    assert {rules.CHART003.id, rules.CHART004.id} <= {f.rule_id for f in audit_odf(SOURCE).findings}
    once, twice = tmp_path / "once.odc", tmp_path / "twice.odc"
    assert apply_answers(SOURCE, once, _plan()).changed
    assert not apply_answers(once, twice, _plan()).changed
    after = OdfDocument.open(twice)
    assert before.storage.read("content.xml") == after.storage.read("content.xml")
    assert once.read_bytes() == twice.read_bytes()
    assert validate(after).count == 0
    assert audit_odf(twice, schema=True).findings == []


def test_chart_numeric_change_is_rejected_before_publication(tmp_path: Path) -> None:
    destination = tmp_path / "wrong.odc"
    assert_refused(apply_answers(SOURCE, destination, [ChangeChartData()]), match="content changed")
    assert not destination.exists()


@pytest.mark.parametrize("profile", ["source", "verify"])
def test_chart_source_profiles_retain_explicit_non_pdf_stages(tmp_path: Path, profile: str) -> None:
    record = execute(
        SOURCE,
        reviewed_plan(SOURCE, _plan(), Pagination.SAME()),
        tmp_path / profile,
        RunSettings(profile=profile_named(profile)),
    )
    assert record.passed, [stage.as_dict() for stage in record.stages]
    assert not (tmp_path / profile / "remediated.pdf").exists()
    if profile == "verify":
        assert any(stage.status == "not-applicable" for stage in record.stages)


def test_chart_production_cannot_pass_without_pdf_assurance(tmp_path: Path) -> None:
    record = execute(
        SOURCE,
        reviewed_plan(SOURCE, _plan(), Pagination.SAME()),
        tmp_path / "production",
        RunSettings(profile=profile_named("production")),
    )
    assert not record.passed
    assert record.failed_stage == "export-source"


@pytest.mark.parametrize(
    "address",
    ["local-table.$B$0", "local-table.$B$2:.$B$4", "local-table.$B$3:.$B$2", "local-table.$Z$1"],
)
def test_chart_local_range_rejects_invalid_bounds(address: str) -> None:
    chart = select_elements(OdfDocument.open(SOURCE).tree(Part.CONTENT), "//chart:chart")[0]
    with pytest.raises(DocumentRefusal, match="range"):
        range_shape(chart, address)


def test_chart_repeats_are_compressed_and_quoted_table_names_resolve() -> None:
    chart = etree.Element(qn("chart", "chart"))
    table = etree.SubElement(chart, qn("table", "table"), {qn("table", "name"): "Fruit's counts"})
    etree.SubElement(
        table, qn("table", "table-column"), {qn("table", "number-columns-repeated"): "1000000000"}
    )
    row = etree.SubElement(
        table, qn("table", "table-row"), {qn("table", "number-rows-repeated"): "1000000000"}
    )
    etree.SubElement(
        row, qn("table", "table-cell"), {qn("table", "number-columns-repeated"): "1000000000"}
    )
    assert range_shape(chart, "'Fruit''s counts'.$A$1:.$B$1000000000") == (1000000000, 2)
    assert len(table) == 2
    assert range_shape(chart, "external.$A$1") is None


def test_chart_external_provider_is_not_fetched_or_echoed(tmp_path: Path) -> None:
    document = OdfDocument.open(SOURCE)
    chart = select_elements(document.tree(Part.CONTENT), "//chart:chart")[0]
    resource = "https://person:secret@invalid.example/private.csv"
    chart.set(qn("xlink", "href"), resource)
    source = document.save(tmp_path / "external.odc")
    report = audit_odf(source)
    assert rules.CHART006.id in {f.rule_id for f in report.findings}
    assert resource not in str(report.as_dict())


def test_chart_has_no_invented_alternative_config_table(tmp_path: Path) -> None:
    plan = tmp_path / "plan.toml"
    plan.write_text('[chart]\nalternative = "Counts"\n')
    with pytest.raises(PlanError):
        load_plan(plan)


@pytest.mark.parametrize("defect", ["categories", "string-value"])
def test_chart_series_category_and_value_consistency_requires_review(
    tmp_path: Path, defect: str
) -> None:
    document = OdfDocument.open(SOURCE)
    tree = document.tree(Part.CONTENT)
    if defect == "categories":
        categories = select_elements(tree, "//chart:categories")[0]
        categories.set(qn("table", "cell-range-address"), "local-table.$A$2")
    else:
        series = select_elements(tree, "//chart:series")[0]
        series.set(qn("chart", "values-cell-range-address"), "local-table.$B$1:.$B$3")
    report = audit_odf(document.save(tmp_path / "inconsistent.odc"))
    assert (rules.CHART010.id if defect == "categories" else rules.CHART011.id) in {
        f.rule_id for f in report.findings
    }


def test_chart_audit_uses_typed_metadata_without_a_report_fact_channel() -> None:
    document = OdfDocument.open(SOURCE)
    metadata = read_metadata(document, None).metadata
    standalone = Report(ReportKind.ODF, SOURCE.name)
    audit_chart(document, standalone, metadata)
    full = audit_odf(SOURCE)
    expected = [
        finding.as_dict() for finding in full.findings if finding.rule.id.startswith("CHART")
    ]
    assert [finding.as_dict() for finding in standalone.findings] == expected
    assert measurement(standalone, ChartMeasurements) == measurement(full, ChartMeasurements)
