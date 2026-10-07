# SPDX-License-Identifier: MPL-2.0
"""Named-link self-test, current-runtime behavior and real pipeline evidence."""

from __future__ import annotations

import json
import runpy
import sys
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from odfa11y import __version__
from odfa11y.cli import main
from odfa11y.errors import ToolFailedError, ToolNotFoundError
from odfa11y.evidence import check_bundle
from odfa11y.external_tools import ToolIdentity
from odfa11y.families.text import write_link_probe
from odfa11y.fidelity import FidelityPolicy
from odfa11y.odf import Family, OdfDocument, PackageStorage, validate
from odfa11y.pdf import (
    ExportSettings,
    audit_pdfua,
    export_pdfua,
    identify_soffice,
    link_descriptions_supported,
    validate_pdfua,
)
from odfa11y.pipeline import PipelineOptions, run_pipeline

from .fixtures import make_minimal_odt
from .pdf_fixtures import annotation_references, dictionary, link_elements, map_link, tagged_writer

if TYPE_CHECKING:
    from collections.abc import Callable

WRITER = "writer_pdf_Export"
SETTINGS = ExportSettings(WRITER)
LINK_BODY = (
    b'<text:p text:style-name="Body">See <text:a xlink:type="simple" '
    b'xlink:href="https://example.test/a">the site</text:a>.</text:p>'
)


def stub_export(*, described: bool) -> Callable[[Path, Path, ExportSettings], Path]:
    def export(source: Path, destination: Path, _settings: ExportSettings) -> Path:
        assert zipfile.is_zipfile(source)  # the probe is a real ODF package
        writer = tagged_writer(["H1", ("P", ["Link"])], link_annotations=1)
        annotation = annotation_references(writer)[0]
        map_link(writer, link_elements(writer)[0], annotation)
        if not described:
            del dictionary(annotation)["/Contents"]
        writer.write(destination)
        return destination

    return export


@pytest.fixture
def probe(tmp_path: Path) -> Path:
    path = tmp_path / "probe.odt"
    write_link_probe(path)
    return path


@pytest.fixture
def reported_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supply explicit identities for doctor output tests without launching native tools."""
    monkeypatch.setattr("odfa11y.cli.commands.find_soffice", lambda _requested: "test-soffice")
    monkeypatch.setattr(
        "odfa11y.cli.commands.identify_soffice",
        lambda _executable: ToolIdentity("LibreOffice", "26.8.0.3"),
    )
    monkeypatch.setattr("odfa11y.cli.commands.find_verapdf", lambda: "test-verapdf")
    monkeypatch.setattr(
        "odfa11y.cli.commands.identify",
        lambda _name, _executable, _arguments: ToolIdentity("veraPDF", "1.30.2"),
    )


def test_the_probe_is_a_readable_text_document_with_one_link(probe: Path) -> None:
    content = zipfile.ZipFile(probe).read("content.xml")
    assert content.count(b"<text:a ") == 1
    kind = OdfDocument.open(probe).kind
    assert kind is not None
    assert kind.family == Family.TEXT


def test_a_described_link_means_supported(probe: Path) -> None:
    assert link_descriptions_supported(probe, SETTINGS, stub_export(described=True))


def test_an_undescribed_link_means_unsupported(probe: Path) -> None:
    assert not link_descriptions_supported(probe, SETTINGS, stub_export(described=False))


def test_an_uninspectable_pdf_is_a_failure_not_a_verdict(probe: Path) -> None:
    def export(_source: Path, destination: Path, _settings: ExportSettings) -> Path:
        destination.write_bytes(b"not a pdf")
        return destination

    with pytest.raises(ToolFailedError):
        link_descriptions_supported(probe, SETTINGS, export)


def test_a_pdf_without_a_hyperlink_is_not_a_supported_verdict(probe: Path) -> None:
    def export(_source: Path, destination: Path, _settings: ExportSettings) -> Path:
        tagged_writer(["H1", "P"]).write(destination)
        return destination

    with pytest.raises(ToolFailedError, match="contains no hyperlink"):
        link_descriptions_supported(probe, SETTINGS, export)


def test_a_missing_libreoffice_propagates(probe: Path, tmp_path: Path) -> None:
    with pytest.raises(ToolNotFoundError):
        link_descriptions_supported(probe, ExportSettings(WRITER, soffice=tmp_path / "absent"))


@pytest.mark.usefixtures("reported_tools")
@pytest.mark.parametrize(("supported", "expected"), [(True, "supported"), (False, "unsupported")])
def test_doctor_reports_the_capability(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    supported: object,
    expected: str,
) -> None:
    monkeypatch.setattr(
        "odfa11y.cli.commands.link_descriptions_supported", lambda _probe, _settings: supported
    )
    assert main(["doctor", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["pdfua_link_descriptions"] == expected
    assert main(["doctor"]) == 0
    assert f"pdfua_link_descriptions: {expected}" in capsys.readouterr().out


def test_doctor_without_libreoffice_still_reports_and_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["doctor", "--soffice", str(tmp_path / "absent"), "--format", "json"]) == 3
    captured = capsys.readouterr()
    assert "error:" in captured.err
    info = json.loads(captured.out)
    assert info["LibreOffice"] is None
    assert info["pdfua_link_descriptions"] is None


@pytest.mark.usefixtures("reported_tools")
def test_doctor_reports_selected_tool_versions(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "odfa11y.cli.commands.link_descriptions_supported", lambda _probe, _settings: True
    )
    assert main(["doctor", "--format", "json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["odfa11y"] == __version__
    assert info["LibreOffice"] == "26.8.0.3"
    assert info["veraPDF"] == "1.30.2"
    assert {"python", "lxml", "pypdf", "pypdfium2", "pillow", "odf_schemas"} <= info.keys()
    assert main(["doctor"]) == 0
    assert "odfa11y:" in capsys.readouterr().out


@pytest.mark.usefixtures("reported_tools")
def test_module_entry_point_runs_the_cli(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "odfa11y.cli.commands.link_descriptions_supported", lambda _probe, _settings: True
    )
    monkeypatch.setattr(sys, "argv", ["odfa11y", "doctor", "--format", "json"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("odfa11y", run_name="__main__")
    assert exit_info.value.code == 0
    assert json.loads(capsys.readouterr().out)["odfa11y"] == __version__


@pytest.mark.integration
def test_doctor_agrees_with_the_audit_of_a_real_export(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    package = PackageStorage(make_minimal_odt(tmp_path / "base.odt"))
    package.write_member(
        "content.xml",
        package.read("content.xml").replace(b"<office:text>", b"<office:text>" + LINK_BODY, 1),
    )
    linked = tmp_path / "linked.odt"
    package.save(linked)
    pdf = export_pdfua(linked, tmp_path / "linked.pdf", ExportSettings(WRITER, soffice=soffice))
    assert "PDF019" in {f.rule_id for f in audit_pdfua(pdf).findings}
    result = validate_pdfua(pdf, executable=external_tool("verapdf"))
    link_failures = {("7.18.1", "2"), ("7.18.5", "2")}
    assert {(f.clause, f.test_number) for f in result.failures} == link_failures

    assert main(["doctor", "--soffice", soffice, "--format", "json"]) == 0
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["LibreOffice"] == identify_soffice(soffice).version
    reported = doctor["pdfua_link_descriptions"]
    assert reported == "supported"

    record = run_pipeline(
        linked, [], FidelityPolicy(), tmp_path / "evidence", PipelineOptions(soffice=soffice)
    )
    assert record.toolchain["LibreOffice"]["pdfua_link_descriptions"] == reported
    assert record.toolchain["LibreOffice"]["version"] == doctor["LibreOffice"]
    evidence = json.loads((tmp_path / "evidence" / "run.json").read_text())
    assert evidence["toolchain"]["LibreOffice"]["pdfua_link_descriptions"] == reported
    assert not any("probe" in name for name in evidence["outputs"])
    assert check_bundle(tmp_path / "evidence") == []


@pytest.mark.integration
@pytest.mark.parametrize("named", [False, True], ids=["unnamed", "explicit-name"])
def test_the_one_link_reproduction_and_explicit_name_control(
    tmp_path: Path, external_tool: Callable[..., str], *, named: bool
) -> None:
    source = Path(__file__).parent / "reproductions" / "unnamed-link.odt"
    assert validate(OdfDocument.open(source)).count == 0
    package = PackageStorage(source)
    assert package.read("content.xml").count(b"<text:a ") == 1
    if named:
        package.write_member(
            "content.xml",
            package.read("content.xml").replace(
                b"<text:a ", b'<text:a office:name="Example site" '
            ),
        )
        source = package.save(tmp_path / "named-link.odt")
        assert validate(OdfDocument.open(source)).count == 0
    pdf = export_pdfua(
        source,
        tmp_path / "link.pdf",
        ExportSettings(WRITER, soffice=external_tool("soffice", "libreoffice")),
    )
    report = audit_pdfua(pdf)
    result = validate_pdfua(pdf, executable=external_tool("verapdf"))
    failures = {(f.clause, f.test_number) for f in result.failures}
    assert failures == (set() if named else {("7.18.1", "2"), ("7.18.5", "2")}), failures
    assert ("PDF019" in {f.rule_id for f in report.findings}) == (not named)
    if named:
        assert report.passed
        assert result.compliant
        record = run_pipeline(
            source,
            [],
            FidelityPolicy(),
            tmp_path / "named-evidence",
            PipelineOptions(soffice=external_tool("soffice", "libreoffice")),
        )
        assert record.passed, record.as_dict()
        assert check_bundle(tmp_path / "named-evidence") == []
