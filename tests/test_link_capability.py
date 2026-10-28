# SPDX-License-Identifier: MPL-2.0
"""Link-description self-test, native Name controls and pipeline evidence."""

from __future__ import annotations

import json
import runpy
import sys
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pypdf.generic import NameObject, TextStringObject

from odfa11y import __version__
from odfa11y.cli import main
from odfa11y.content import LinkDescription, document_links, link_fingerprint
from odfa11y.errors import ToolFailedError, ToolNotFoundError
from odfa11y.evidence import check_bundle
from odfa11y.families.text import SetLinkDescriptions
from odfa11y.families.text.probes import LINK_PURPOSE, PROBES, write_link_probe
from odfa11y.native.export import ExportSettings, export_pdfua, identify_soffice
from odfa11y.native.probes import (
    CapabilityResult,
    CapabilityStatus,
    ProbeCache,
    ProbeExecution,
    ProbeId,
)
from odfa11y.native.process import ToolIdentity
from odfa11y.odf import Family, OdfDocument, PackageStorage, validate
from odfa11y.pdf import audit_pdfua, validate_pdfua
from odfa11y.pdf.fidelity import FidelityPolicy
from odfa11y.pipeline import PipelineOptions, run_pipeline

from .fixtures import make_minimal_odt
from .pdf_fixtures import annotation_references, dictionary, link_elements, map_link, tagged_writer
from .probe_fixtures import conclusive_probe
from .reviewed_plans import reviewed_plan

if TYPE_CHECKING:
    from collections.abc import Callable

    from odfa11y.native.probes import (
        CapabilityProbe,
    )

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
        dictionary(annotation)[NameObject("/Contents")] = TextStringObject(
            "ODFA11y reviewed link purpose."
        )
        if not described:
            del dictionary(annotation)["/Contents"]
        writer.write(destination)
        return destination

    return export


@pytest.fixture
def probe(tmp_path: Path) -> Path:
    return write_link_probe(tmp_path)


@pytest.fixture
def reported_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supply explicit identities for doctor output tests without launching native tools."""
    monkeypatch.setattr(
        "odfa11y.pipeline.diagnostics.find_soffice", lambda _requested: "test-soffice"
    )
    monkeypatch.setattr(
        "odfa11y.pipeline.diagnostics.identify_soffice",
        lambda _executable: ToolIdentity("LibreOffice", "26.8.0.3"),
    )
    monkeypatch.setattr("odfa11y.pipeline.diagnostics.find_verapdf", lambda: "test-verapdf")
    monkeypatch.setattr(
        "odfa11y.pipeline.diagnostics.identify",
        lambda _name, _executable, _arguments: ToolIdentity("veraPDF", "1.30.3"),
    )


def test_the_probe_is_a_readable_text_document_with_one_link(probe: Path) -> None:
    content = zipfile.ZipFile(probe).read("content.xml")
    assert content.count(b"<text:a ") == 1
    kind = OdfDocument.open(probe).kind
    assert kind is not None
    assert kind.family == Family.TEXT


def test_a_described_link_means_supported() -> None:
    assert probe_result(stub_export(described=True)).result.status == CapabilityStatus.SUPPORTED


def test_an_undescribed_link_means_unsupported() -> None:
    assert probe_result(stub_export(described=False)).result.status == CapabilityStatus.UNSUPPORTED


def test_an_uninspectable_pdf_is_a_failure_not_a_verdict() -> None:
    def export(_source: Path, destination: Path, _settings: ExportSettings) -> Path:
        destination.write_bytes(b"not a pdf")
        return destination

    execution = probe_result(export)
    assert isinstance(execution.error, ToolFailedError)
    assert execution.result.status == CapabilityStatus.NOT_TESTED


def test_a_pdf_without_a_hyperlink_is_not_a_supported_verdict() -> None:
    def export(_source: Path, destination: Path, _settings: ExportSettings) -> Path:
        tagged_writer(["H1", "P"]).write(destination)
        return destination

    execution = probe_result(export)
    assert isinstance(execution.error, ToolFailedError)
    assert "contains no hyperlink" in str(execution.error)
    assert execution.result.status == CapabilityStatus.NOT_TESTED


def test_a_missing_libreoffice_propagates(tmp_path: Path) -> None:
    execution = ProbeCache().run(
        PROBES[0],
        ToolIdentity("LibreOffice", "26.8.1.1"),
        ExportSettings(WRITER, soffice=tmp_path / "absent"),
    )
    assert isinstance(execution.error, ToolNotFoundError)
    assert execution.result.status == CapabilityStatus.NOT_TESTED


@pytest.mark.usefixtures("reported_tools")
@pytest.mark.parametrize(("supported", "expected"), [(True, "supported"), (False, "unsupported")])
def test_doctor_reports_the_capability(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    supported: bool,
    expected: str,
) -> None:
    def verdict(
        _cache: ProbeCache,
        descriptor: CapabilityProbe,
        identity: ToolIdentity,
        _settings: ExportSettings,
        **_kwargs: object,
    ) -> ProbeExecution:
        return ProbeExecution(
            CapabilityResult(
                descriptor.id,
                descriptor.family,
                CapabilityStatus.SUPPORTED if supported else CapabilityStatus.UNSUPPORTED,
                identity,
            )
        )

    monkeypatch.setattr(ProbeCache, "run", verdict)
    assert main(["doctor", "--format", "json"]) == 0
    assert (
        next(
            item["status"]
            for item in json.loads(capsys.readouterr().out)["toolchain"]["capabilities"]
            if item["id"] == "link-descriptions"
        )
        == expected
    )
    assert main(["doctor"]) == 0
    assert f"text.link-descriptions: {expected}" in capsys.readouterr().out


def test_doctor_without_libreoffice_still_reports_and_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["doctor", "--soffice", str(tmp_path / "absent"), "--format", "json"]) == 3
    captured = capsys.readouterr()
    assert "error:" in captured.err
    info = json.loads(captured.out)
    assert info["toolchain"]["libreoffice"] is None
    assert len(info["toolchain"]["capabilities"]) == len(ProbeId)
    assert all(result["status"] == "not-tested" for result in info["toolchain"]["capabilities"])


@pytest.mark.usefixtures("reported_tools")
def test_doctor_reports_selected_tool_versions(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(ProbeCache, "run", conclusive_probe)
    assert main(["doctor", "--format", "json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["odfa11y"] == __version__
    assert info["toolchain"]["libreoffice"]["version"] == "26.8.0.3"
    assert info["toolchain"]["verapdf"]["version"] == "1.30.3"
    assert {"python", "schema_versions", "libraries", "toolchain"} <= info.keys()
    assert {"lxml", "pypdf", "pypdfium2", "pillow"} <= info["libraries"].keys()
    assert main(["doctor"]) == 0
    assert "odfa11y:" in capsys.readouterr().out


@pytest.mark.usefixtures("reported_tools")
def test_module_entry_point_runs_the_cli(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(ProbeCache, "run", conclusive_probe)
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
    assert doctor["toolchain"]["libreoffice"]["version"] == identify_soffice(soffice).version
    reported = next(
        item["status"]
        for item in doctor["toolchain"]["capabilities"]
        if item["id"] == "link-descriptions"
    )
    titled_probe = write_link_probe(tmp_path)
    probe_pdf = export_pdfua(
        titled_probe, tmp_path / "title-probe.pdf", ExportSettings(WRITER, soffice=soffice)
    )
    expected_support = (
        "unsupported"
        if "PDF019" in {f.rule_id for f in audit_pdfua(probe_pdf).findings}
        else "supported"
    )
    assert reported == expected_support

    document = OdfDocument.open(linked)
    record = run_pipeline(
        linked,
        reviewed_plan(
            linked,
            [
                SetLinkDescriptions({
                    "content/link[1]": LinkDescription(
                        LINK_PURPOSE, link_fingerprint(document, document_links(document)[0])
                    )
                })
            ],
            FidelityPolicy(),
        ),
        tmp_path / "evidence",
        PipelineOptions(soffice=soffice),
    )
    assert (
        next(
            item.status.value
            for item in record.toolchain.capabilities
            if item.id == ProbeId.LINK_DESCRIPTIONS
        )
        == reported
    )
    assert record.toolchain.libreoffice is not None
    assert record.toolchain.libreoffice.version == doctor["toolchain"]["libreoffice"]["version"]
    evidence = json.loads((tmp_path / "evidence" / "run.json").read_text())
    assert (
        next(
            item["status"]
            for item in evidence["toolchain"]["capabilities"]
            if item["id"] == "link-descriptions"
        )
        == reported
    )
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
            reviewed_plan(source, [], FidelityPolicy()),
            tmp_path / "named-evidence",
            PipelineOptions(soffice=external_tool("soffice", "libreoffice")),
        )
        assert record.passed, record.as_dict()
        assert check_bundle(tmp_path / "named-evidence") == []


def probe_result(export: Callable[[Path, Path, ExportSettings], Path]) -> ProbeExecution:
    """Execute the registered link experiment with an independent exporter control.

    Returns
    -------
    ProbeExecution
        The measured result and any controlled error.

    """
    return ProbeCache().run(
        PROBES[0], ToolIdentity("LibreOffice", "26.8.1.1"), SETTINGS, export=export
    )
