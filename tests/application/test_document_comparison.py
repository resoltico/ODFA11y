# SPDX-License-Identifier: MPL-2.0
"""Core document comparison owns input refusal, private renders and source identity."""

import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from odfa11y.application.native import NativeTools
from odfa11y.application.tools import Tools
from odfa11y.errors import DocumentRefusal, PackageError, ToolFailure
from odfa11y.plans.fidelity import Pagination
from odfa11y.run.comparison import compare_documents, is_pdf
from odfa11y.run.native import export_document
from tests.fixtures.native import refusing
from tests.fixtures.native_resources import writer_resource
from tests.fixtures.pdf import text_pdf
from tests.fixtures.writer import make_minimal_odt
lazy from odfa11y.native.export import ExportSettings


def test_core_comparison_preflights_both_inputs_before_export(
    native_tools: NativeTools, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    calls: list[object] = []
    native_tools = replace(native_tools, export=refusing(calls))
    with pytest.raises(FileNotFoundError):
        compare_documents(
            source, tmp_path / "missing", Pagination.SAME(), native_tools=native_tools
        )
    assert not calls


def test_core_pdf_probe_refuses_fifo_without_opening(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if sys.platform == "win32":
        pytest.skip("POSIX FIFO")
    fifo = tmp_path / "input"
    os.mkfifo(fifo)
    calls: list[object] = []
    monkeypatch.setattr("os.open", lambda *args: calls.append(args))
    with pytest.raises(PackageError, match="regular file"):
        is_pdf(fifo)
    assert not calls


def test_core_pdf_comparison_keeps_original_report_identity(tmp_path: Path) -> None:
    source = text_pdf(tmp_path / "source.pdf", [["Example"]])
    candidate = text_pdf(tmp_path / "candidate.pdf", [["Example"]])
    before = (source.read_bytes(), candidate.read_bytes())
    events: list[tuple[str, str]] = []
    report = compare_documents(
        source,
        candidate,
        Pagination.SAME(),
        tools=Tools(),
        on_progress=lambda event: events.append((event.step, event.state)),
    )
    assert report.error_count == 0
    assert report.sources == (candidate, source)
    assert report.subject == "candidate.pdf vs source.pdf"
    assert events == [("compare-fidelity", "running"), ("compare-fidelity", "passed")]
    assert (source.read_bytes(), candidate.read_bytes()) == before


def test_core_odf_comparison_keeps_renders_alive_and_cleans_scratch(
    native_tools: NativeTools, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    candidate = make_minimal_odt(tmp_path / "candidate.odt")
    profiles: list[Path] = []
    rendered: list[Path] = []

    def render(path: Path, destination: Path, settings: ExportSettings) -> Path:
        assert path in {source, candidate}
        assert settings.profile_dir is not None
        profiles.append(Path(settings.profile_dir))
        rendered.append(destination)
        return text_pdf(destination, [["Example"]])

    native_tools = replace(native_tools, export=render)
    report = compare_documents(source, candidate, Pagination.SAME(), native_tools=native_tools)
    assert report.error_count == 0
    assert profiles[0] == profiles[1]
    assert all(not path.exists() for path in rendered)
    assert not profiles[0].parent.exists()
    assert report.sources == (candidate, source)
    assert str(profiles[0].parent) not in str(report.as_dict())


def test_guarded_core_export_refuses_unresolved_resources_before_native_boundary(
    native_tools: NativeTools, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = writer_resource(tmp_path, "https://example.test/image.png")
    before = source.read_bytes()
    calls: list[object] = []
    native_tools = replace(native_tools, export=refusing(calls))
    with pytest.raises(DocumentRefusal, match="resource"):
        export_document(
            source, tmp_path / "out.pdf", Tools(soffice="missing-tool"), native_tools=native_tools
        )
    assert not calls
    assert source.read_bytes() == before
    assert not (tmp_path / "out.pdf").exists()


def test_core_comparison_cleans_private_render_after_candidate_export_failure(
    native_tools: NativeTools, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    candidate = make_minimal_odt(tmp_path / "candidate.odt")
    before = (source.read_bytes(), candidate.read_bytes())
    rendered: list[Path] = []

    def render(path: Path, destination: Path, _settings: ExportSettings) -> Path:
        if path == candidate:
            msg = "Candidate native export failed"
            raise ToolFailure(msg)
        rendered.append(destination)
        return text_pdf(destination, [["Example"]])

    native_tools = replace(native_tools, export=render)
    with pytest.raises(ToolFailure, match="Candidate native export failed"):
        compare_documents(source, candidate, Pagination.SAME(), native_tools=native_tools)
    assert rendered
    assert not rendered[0].parent.exists()
    assert (source.read_bytes(), candidate.read_bytes()) == before
