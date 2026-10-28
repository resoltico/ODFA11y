# SPDX-License-Identifier: MPL-2.0
"""Core document comparison owns input refusal, private renders and source identity."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from odfa11y.errors import PackageError, ToolFailedError
from odfa11y.fidelity import FidelityPolicy
from odfa11y.pipeline import NativeOptions, compare_documents, export_document, is_pdf

from .fixtures import make_minimal_odt
from .native_resource_fixtures import writer_resource
from .pdf_fixtures import text_pdf

if TYPE_CHECKING:
    from collections.abc import Callable

    from odfa11y.pdf import ExportSettings


def test_core_comparison_preflights_both_inputs_before_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    calls: list[object] = []
    monkeypatch.setattr(
        "odfa11y.pipeline.comparison.export_pdfua", lambda *args: calls.append(args)
    )
    with pytest.raises(FileNotFoundError):
        compare_documents(source, tmp_path / "missing", FidelityPolicy())
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
        FidelityPolicy(),
        options=NativeOptions(on_progress=lambda event: events.append((event.step, event.state))),
    )
    assert report.passed
    assert report.sources == (candidate, source)
    assert report.subject == "candidate.pdf vs source.pdf"
    assert events == [("compare-fidelity", "running"), ("compare-fidelity", "passed")]
    assert (source.read_bytes(), candidate.read_bytes()) == before


def test_core_odf_comparison_keeps_renders_alive_and_cleans_scratch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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

    monkeypatch.setattr("odfa11y.pipeline.comparison.export_pdfua", render)
    report = compare_documents(source, candidate, FidelityPolicy())
    assert report.passed
    assert profiles[0] == profiles[1]
    assert all(not path.exists() for path in rendered)
    assert not profiles[0].parent.exists()
    assert report.sources == (candidate, source)
    assert str(profiles[0].parent) not in str(report.as_dict())


def test_guarded_core_export_refuses_unresolved_resources_before_native_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = writer_resource(tmp_path, "https://example.test/image.png")
    before = source.read_bytes()
    calls: list[object] = []
    monkeypatch.setattr("odfa11y.pipeline.native.export_pdfua", lambda *args: calls.append(args))
    with pytest.raises(ToolFailedError, match="rendering dependencies"):
        export_document(source, tmp_path / "out.pdf", NativeOptions(soffice="missing-tool"))
    assert not calls
    assert source.read_bytes() == before
    assert not (tmp_path / "out.pdf").exists()


@pytest.mark.integration
def test_guarded_core_export_with_real_libreoffice(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    before = source.read_bytes()
    destination = tmp_path / "out.pdf"
    exported = export_document(
        source, destination, NativeOptions(soffice=external_tool("soffice", "libreoffice"))
    )
    assert exported == destination
    assert is_pdf(exported)
    assert source.read_bytes() == before


def test_core_comparison_cleans_private_render_after_candidate_export_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    candidate = make_minimal_odt(tmp_path / "candidate.odt")
    before = (source.read_bytes(), candidate.read_bytes())
    rendered: list[Path] = []

    def render(path: Path, destination: Path, _settings: ExportSettings) -> Path:
        if path == candidate:
            msg = "Candidate native export failed"
            raise ToolFailedError(msg)
        rendered.append(destination)
        return text_pdf(destination, [["Example"]])

    monkeypatch.setattr("odfa11y.pipeline.comparison.export_pdfua", render)
    with pytest.raises(ToolFailedError, match="Candidate native export failed"):
        compare_documents(source, candidate, FidelityPolicy())
    assert rendered
    assert not rendered[0].parent.exists()
    assert (source.read_bytes(), candidate.read_bytes()) == before
