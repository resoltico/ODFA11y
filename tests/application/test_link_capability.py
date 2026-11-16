# SPDX-License-Identifier: AGPL-3.0-only
"""Link-description self-test, native Name controls and pipeline evidence."""

import json
import runpy
import sys
import zipfile
from dataclasses import replace
lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest
from pypdf.generic import NameObject, TextStringObject

from odfa11y import __version__
from odfa11y.application.native import NativeTools
from odfa11y.cli import main
from odfa11y.errors import IoFailure, ToolFailure
from odfa11y.families import probes as probe_operations
from odfa11y.families.probes import (
    CapabilityResult,
    CapabilityStatus,
    ProbeExecution,
    ProbeId,
    measure_probe,
)
from odfa11y.families.text.probes import PROBES, write_link_probe
from odfa11y.native.libreoffice import ExportSettings
from odfa11y.odf import Family, OdfDocument
from odfa11y.tool_identity import ToolIdentity
from tests.fixtures.native import export_settings
from tests.fixtures.pdf import (
    annotation_references,
    dictionary,
    link_elements,
    map_link,
    tagged_writer,
)
from tests.fixtures.probes import conclusive_probe
lazy from odfa11y.families.probes import CapabilityProbe

WRITER = "writer_pdf_Export"
SETTINGS = export_settings(WRITER)
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
def reported_tools(native_tools: NativeTools, monkeypatch: pytest.MonkeyPatch) -> NativeTools:
    """Supply explicit identities for doctor output tests without launching native tools."""
    native_tools = replace(native_tools, locate=lambda _requested: "test-soffice")
    native_tools = replace(
        native_tools,
        identify=lambda _executable, **_options: ToolIdentity("LibreOffice", "26.8.0.3"),
    )
    native_tools = replace(native_tools, validator=lambda _requested=None: "test-verapdf")
    native_tools = replace(
        native_tools,
        identify_validator=lambda _name, _executable, _arguments, **_options: ToolIdentity(
            "veraPDF", "1.30.3"
        ),
    )
    return native_tools


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
    assert isinstance(execution.error, ToolFailure)
    assert execution.result.status == CapabilityStatus.NOT_TESTED


def test_a_pdf_without_a_hyperlink_is_not_a_supported_verdict() -> None:
    def export(_source: Path, destination: Path, _settings: ExportSettings) -> Path:
        tagged_writer(["H1", "P"]).write(destination)
        return destination

    execution = probe_result(export)
    assert isinstance(execution.error, ToolFailure)
    assert "contains no hyperlink" in str(execution.error)
    assert execution.result.status == CapabilityStatus.NOT_TESTED


def test_a_missing_libreoffice_propagates(tmp_path: Path) -> None:
    execution = measure_probe(
        PROBES[0],
        ToolIdentity("LibreOffice", "26.8.1.1"),
        export_settings(WRITER, soffice=tmp_path / "absent"),
    )
    assert isinstance(execution.error, IoFailure)
    assert execution.result.status == CapabilityStatus.NOT_TESTED


@pytest.mark.usefixtures("reported_tools")
@pytest.mark.parametrize(("supported", "expected"), [(True, "supported"), (False, "unsupported")])
def test_doctor_reports_the_capability(
    reported_tools: NativeTools,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    supported: bool,
    expected: str,
) -> None:
    native_tools = reported_tools

    def verdict(
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

    monkeypatch.setattr(probe_operations, "measure_probe", verdict)
    assert main(["doctor", "--format", "json"], native_tools=native_tools) == 0
    assert (
        next(
            item["status"]
            for item in json.loads(capsys.readouterr().out)["capabilities"]
            if item["id"] == "link-descriptions"
        )
        == expected
    )
    assert main(["doctor"], native_tools=native_tools) == 0
    assert f"link-descriptions: {expected}" in capsys.readouterr().out


def test_doctor_without_libreoffice_still_reports_and_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["doctor", "--soffice", str(tmp_path / "absent"), "--format", "json"]) == 3
    captured = capsys.readouterr()
    assert "error:" in captured.err
    info = json.loads(captured.out)
    assert info["toolchain"]["libreoffice"] is None
    assert len(info["capabilities"]) == len(ProbeId)
    assert all(result["status"] == "not-tested" for result in info["capabilities"])


@pytest.mark.usefixtures("reported_tools")
def test_doctor_reports_selected_tool_versions(
    reported_tools: NativeTools, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    native_tools = reported_tools
    monkeypatch.setattr(probe_operations, "measure_probe", conclusive_probe)
    assert main(["doctor", "--format", "json"], native_tools=native_tools) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["odfa11y"] == __version__
    assert info["toolchain"]["libreoffice"]["version"] == "26.8.0.3"
    assert info["toolchain"]["verapdf"]["version"] == "1.30.3"
    assert {"python", "schema_versions", "libraries", "toolchain"} <= info.keys()
    assert {"lxml", "pypdf", "pypdfium2", "pillow"} <= info["libraries"].keys()
    assert main(["doctor"], native_tools=native_tools) == 0
    assert "odfa11y:" in capsys.readouterr().out


@pytest.mark.usefixtures("reported_tools")
def test_module_entry_point_runs_the_cli(
    reported_tools: NativeTools, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    native_tools = reported_tools
    monkeypatch.setattr(probe_operations, "measure_probe", conclusive_probe)
    monkeypatch.setattr(sys, "argv", ["odfa11y", "doctor", "--format", "json"])
    monkeypatch.setattr("odfa11y.cli.main", lambda: main(native_tools=native_tools))
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("odfa11y", run_name="__main__")
    assert exit_info.value.code == 0
    assert json.loads(capsys.readouterr().out)["odfa11y"] == __version__


def probe_result(export: Callable[[Path, Path, ExportSettings], Path]) -> ProbeExecution:
    """Execute the registered link experiment with an independent exporter control.

    Returns
    -------
    ProbeExecution
        The measured result and any controlled error.

    """
    return measure_probe(
        PROBES[0], ToolIdentity("LibreOffice", "26.8.1.1"), SETTINGS, export=export
    )
