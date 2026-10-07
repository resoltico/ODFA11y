# SPDX-License-Identifier: MPL-2.0
"""Check SARIF schema, source identity, logical semantics and disclosure boundaries."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from odfa11y.audit import audit_odf
from odfa11y.pdf import check_pdfua
from odfa11y.report import Finding, Location, Report, Severity, render_reports, rules

from .documents import Variant, make_flat, make_package
from .test_verapdf import report_xml, stub

SCHEMA = Path(__file__).parent / "data/sarif/sarif-schema-2.1.0.json"


def _source(root: Path, name: str) -> Path:
    source = root / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"independent artifact")
    return source


def _render(reports: list[Report], root: Path) -> dict:
    payload = json.loads(render_reports(reports, output_format="sarif", source_root=root))
    schema = json.loads(SCHEMA.read_bytes())
    Draft7Validator.check_schema(schema)
    Draft7Validator(schema, format_checker=Draft7Validator.FORMAT_CHECKER).validate(payload)
    return payload


def test_official_schema_identity_and_negative_control() -> None:
    assert hashlib.sha256(SCHEMA.read_bytes()).hexdigest() == (
        "ad6db49878699b091f3eeb765b6e29e92a34bad4da88664d000c923b549c3a25"
    )
    schema = json.loads(SCHEMA.read_bytes())
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert not Draft7Validator(schema).is_valid({"version": "2.1.0", "runs": [], "secret": "x"})


def test_registered_rules_levels_remedies_and_logical_locations(tmp_path: Path) -> None:
    source = _source(tmp_path, "sample.odt")
    report = Report(kind="odf", subject="ignored display", sources=(source,))
    report.add(rules.META001, location=Location("metadata/title", "meta.xml"))
    report.add(rules.TXT021, location=Location.named("content", "table", "north/south"))
    report.add(rules.TXT004)
    run = _render([report], tmp_path)["runs"][0]
    descriptors = run["tool"]["driver"]["rules"]
    assert [entry["id"] for entry in descriptors] == ["META001", "TXT004", "TXT021"]
    assert [item["level"] for item in run["results"]] == ["error", "warning", "note"]
    for result in run["results"]:
        assert descriptors[result["ruleIndex"]]["id"] == result["ruleId"]
        assert "region" not in result["locations"][0]["physicalLocation"]
    first = run["results"][0]
    assert first["properties"]["remedy"] == "document.title"
    assert first["locations"][0]["properties"] == {"packageMember": "meta.xml"}
    assert first["locations"][0]["logicalLocations"] == [{"fullyQualifiedName": "metadata/title"}]
    assert "logicalLocations" not in run["results"][2]["locations"][0]


def test_artifact_uris_distinguish_duplicate_names_and_escape_reserved_characters(
    tmp_path: Path,
) -> None:
    first = _source(tmp_path, "a folder/report #1.odt")
    second = _source(tmp_path, "other/report #1.odt")
    report = Report(
        kind="fidelity", subject="nonsense label: not a filename", sources=(first, second)
    )
    report.add(rules.FID003)
    run = _render([report], tmp_path)["runs"][0]
    assert run["artifacts"] == [
        {"location": {"uri": "a%20folder/report%20%231.odt"}},
        {"location": {"uri": "other/report%20%231.odt"}},
    ]
    assert [
        loc["physicalLocation"]["artifactLocation"]["index"]
        for loc in run["results"][0]["locations"]
    ] == [0, 1]


def test_multiple_reports_share_artifact_identity(tmp_path: Path) -> None:
    source = _source(tmp_path, "sample.pdf")
    reports = [Report(kind="pdf", subject="x", sources=(source,)) for _ in range(2)]
    for report in reports:
        report.add(rules.PDF001)
    run = _render(reports, tmp_path)["runs"][0]
    assert len(run["artifacts"]) == 1
    assert len(run["results"]) == 2


def test_package_and_flat_findings_have_equivalent_logical_locations(tmp_path: Path) -> None:
    variant = Variant(body='<draw:frame draw:name="portrait"><draw:image/></draw:frame>')
    reports = []
    for name, make in (("package", make_package), ("flat", make_flat)):
        directory = tmp_path / name
        directory.mkdir()
        source = make(directory, "text", variant)
        report = audit_odf(source)
        assert report.sources == (source,)
        reports.append(report)
    results = _render(reports, tmp_path)["runs"][0]["results"]
    graphics = [result for result in results if result["ruleId"] == "TXT010"]
    assert len(graphics) == 2
    assert (
        graphics[0]["locations"][0]["logicalLocations"]
        == graphics[1]["locations"][0]["logicalLocations"]
    )


def test_sarif_excludes_arbitrary_content_paths_and_credentials(tmp_path: Path) -> None:
    source = _source(tmp_path, "sample.odb")
    connection = "postgres://alice:super-secret@database/private"
    report = Report(
        kind="odf", subject=str(source), sources=(source,), metadata={"url": connection}
    )
    report.add(rules.META001, f"{connection} at {source}", details={"connection": connection})
    rendered = render_reports([report], output_format="sarif", source_root=tmp_path)
    assert connection not in rendered
    assert "super-secret" not in rendered
    assert str(tmp_path) not in rendered
    assert str(source) not in rendered
    assert json.loads(rendered)["runs"][0]["results"][0]["message"]["text"] == rules.META001.title


@pytest.mark.parametrize(
    "label",
    [
        "/Users/alice/secret",
        "content/frame[name=/tmp/secret]",
        "content/frame[name=https%3A%2F%2Fu%3Ap%40host%2F]",
    ],
)
def test_unsafe_logical_labels_are_rejected(tmp_path: Path, label: str) -> None:
    report = Report(kind="odf", subject="x", sources=(_source(tmp_path, "x.odt"),))
    report.add(rules.TXT010, location=Location(label))
    with pytest.raises(ValueError, match="unsafe path or credential"):
        _render([report], tmp_path)


def test_sources_outside_root_and_symlink_escape_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = _source(tmp_path, "outside.odt")
    link = root / "escape.odt"
    link.symlink_to(outside)
    for source in (outside, link):
        report = Report(kind="odf", subject="x", sources=(source,))
        with pytest.raises(ValueError, match="within the source root"):
            _render([report], root)


def test_missing_root_source_identity_and_unregistered_rules_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="explicit source root"):
        render_reports([], output_format="sarif")
    with pytest.raises(ValueError, match="explicit source identities"):
        _render([Report(kind="odf", subject="sample.odt")], tmp_path)
    report = Report(kind="odf", subject="x", sources=(_source(tmp_path, "x.odt"),))
    report.findings.append(Finding("UNKNOWN", Severity.ERROR, "x", "x"))
    with pytest.raises(ValueError, match="registered rules"):
        _render([report], tmp_path)


def test_missing_source_is_private_and_empty_report_is_valid(tmp_path: Path) -> None:
    source = tmp_path / "missing-secret.odt"
    report = Report(kind="odf", subject="x", sources=(source,))
    with pytest.raises(ValueError, match=r"^SARIF source identity cannot be resolved\.$"):
        _render([report], tmp_path)
    assert _render([], tmp_path)["runs"][0]["results"] == []


def test_verapdf_report_keeps_pdf_identity_independent_of_display_subject(tmp_path: Path) -> None:
    source = _source(tmp_path, "actual.pdf")
    executable = stub(tmp_path, report_xml(compliant=False), status=1)
    report, result = check_pdfua(source, subject="safe label", executable=executable)
    assert result is not None
    assert report.sources == (source,)
    run = _render([report], tmp_path)["runs"][0]
    assert run["artifacts"] == [{"location": {"uri": "actual.pdf"}}]
    assert run["results"][0]["ruleId"] == "VERA001"


def test_root_must_be_directory_and_in_root_aliases_share_identity(tmp_path: Path) -> None:
    source = _source(tmp_path, "original.odt")
    with pytest.raises(ValueError, match="existing directory"):
        _render([], source)
    link = tmp_path / "alias.odt"
    link.symlink_to(source)
    report = Report(kind="fidelity", subject="x", sources=(source, link))
    report.add(rules.FID003)
    run = _render([report], tmp_path)["runs"][0]
    assert len(run["artifacts"]) == 1
    assert all(
        location["physicalLocation"]["artifactLocation"]["index"] == 0
        for location in run["results"][0]["locations"]
    )
