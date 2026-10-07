# SPDX-License-Identifier: MPL-2.0
"""Native chart metadata edits preserve its data, references and source-only boundary."""

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
from odfa11y.families import adapter_for
from odfa11y.families.chart.ranges import range_shape
from odfa11y.fidelity import FidelityPolicy
from odfa11y.odf import OdfDocument, Part, qn, select_elements, validate
from odfa11y.pipeline import PipelineOptions, run_pipeline
from odfa11y.remediation import SetMetadata, remediate

SOURCE = Path(__file__).parent / "family_corpus/fruit-chart.odc"


def _plan() -> list[Operation]:
    return [
        SetMetadata(
            title="Fruit counts", description="Three apples and four pears", language="en-US"
        )
    ]


@dataclass(frozen=True, slots=True)
class ChangeChartData(Operation):
    """Negative control changes a numerical value without changing its display string."""

    name: ClassVar[str] = "change_chart_data"

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        cell = select_elements(document.edit(Part.CONTENT), "//table:table-cell[@office:value]")[0]
        cell.set(qn("office", "value"), "999")
        return (Outcome(self.name, Status.APPLIED, "Changed data", count=1),)


def test_chart_native_source_and_metadata_preserve_all_chart_xml(tmp_path: Path) -> None:
    before = OdfDocument.open(SOURCE)
    assert validate(before).count == 0
    assert {"CHART002", "CHART003"} <= {f.rule_id for f in audit_odf(SOURCE).findings}
    once, twice = tmp_path / "once.odc", tmp_path / "twice.odc"
    assert remediate(SOURCE, once, _plan()).changed
    assert not remediate(once, twice, _plan()).changed
    after = OdfDocument.open(twice)
    assert adapter_for(before.kind).snapshot(before) == adapter_for(after.kind).snapshot(after)
    assert before.storage.read("content.xml") == after.storage.read("content.xml")
    assert once.read_bytes() == twice.read_bytes()
    assert validate(after).count == 0
    assert audit_odf(twice, schema=True).findings == []


def test_chart_numeric_change_is_rejected_before_publication(tmp_path: Path) -> None:
    destination = tmp_path / "wrong.odc"
    with pytest.raises(RemediationError, match="content changed"):
        remediate(SOURCE, destination, [ChangeChartData()])
    assert not destination.exists()


@pytest.mark.parametrize("profile", ["inspect", "verify"])
def test_chart_source_profiles_retain_explicit_non_pdf_stages(tmp_path: Path, profile: str) -> None:
    record = run_pipeline(
        SOURCE, _plan(), FidelityPolicy(), tmp_path / profile, PipelineOptions(profile=profile)
    )
    assert record.passed, [stage.as_dict() for stage in record.stages]
    assert not (tmp_path / profile / "remediated.pdf").exists()
    if profile == "verify":
        assert any(stage.status == "not-applicable" for stage in record.stages)


def test_chart_production_cannot_pass_without_pdf_assurance(tmp_path: Path) -> None:
    record = run_pipeline(
        SOURCE,
        _plan(),
        FidelityPolicy(),
        tmp_path / "production",
        PipelineOptions(profile="production"),
    )
    assert not record.passed
    assert record.failed_stage == "export-source"


@pytest.mark.parametrize(
    "address",
    ["local-table.$B$0", "local-table.$B$2:.$B$4", "local-table.$B$3:.$B$2", "local-table.$Z$1"],
)
def test_chart_local_range_rejects_invalid_bounds(address: str) -> None:
    chart = select_elements(OdfDocument.open(SOURCE).tree(Part.CONTENT), "//chart:chart")[0]
    with pytest.raises(RemediationError, match="range"):
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
    chart = select_elements(document.edit(Part.CONTENT), "//chart:chart")[0]
    resource = "https://person:secret@invalid.example/private.csv"
    chart.set(qn("xlink", "href"), resource)
    source = document.save(tmp_path / "external.odc")
    report = audit_odf(source)
    assert "CHART005" in {f.rule_id for f in report.findings}
    assert resource not in str(report.as_dict())


def test_chart_has_no_invented_alternative_config_table(tmp_path: Path) -> None:
    plan = tmp_path / "plan.toml"
    plan.write_text('[chart]\nalternative = "Counts"\n')
    with pytest.raises(ConfigError):
        load_config(plan)


@pytest.mark.parametrize("defect", ["categories", "string-value"])
def test_chart_series_category_and_value_consistency_requires_review(
    tmp_path: Path, defect: str
) -> None:
    document = OdfDocument.open(SOURCE)
    tree = document.edit(Part.CONTENT)
    if defect == "categories":
        categories = select_elements(tree, "//chart:categories")[0]
        categories.set(qn("table", "cell-range-address"), "local-table.$A$2")
    else:
        series = select_elements(tree, "//chart:series")[0]
        series.set(qn("chart", "values-cell-range-address"), "local-table.$B$1:.$B$3")
    report = audit_odf(document.save(tmp_path / "inconsistent.odc"))
    assert "CHART006" in {f.rule_id for f in report.findings}
