# SPDX-License-Identifier: MPL-2.0
"""Core tool inspection returns facts and probe failures without rendering a UI."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from odfa11y.errors import ToolFailedError, ToolNotFoundError, UnsupportedKindError
from odfa11y.external_tools import ToolIdentity
from odfa11y.families import REGISTRY
from odfa11y.odf import Family, OdfDocument
from odfa11y.pipeline import diagnostics
from odfa11y.pipeline.native import NativeOptions

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.pdf import ExportSettings


def identities(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostics, "find_soffice", lambda _requested: "soffice")
    monkeypatch.setattr(diagnostics, "find_verapdf", lambda: "verapdf")
    monkeypatch.setattr(
        diagnostics, "identify_soffice", lambda _executable: ToolIdentity("LibreOffice", "26.8")
    )
    monkeypatch.setattr(diagnostics, "identify", lambda *_args: ToolIdentity("veraPDF", "1.28"))


@pytest.mark.parametrize("supported", [False, True])
def test_core_inspection_uses_real_registered_probe_and_returns_no_ui(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *, supported: bool
) -> None:
    identities(monkeypatch)
    visited: list[Path] = []

    def capability(source: Path, settings: ExportSettings) -> bool:
        visited.append(source)
        assert OdfDocument.open(source).kind is not None
        assert settings.pdf_filter == REGISTRY[Family.TEXT].pdf_filter
        assert settings.soffice == "selected-soffice"
        assert settings.timeout == 7
        return supported

    monkeypatch.setattr(diagnostics, "link_descriptions_supported", capability)
    facts, error = diagnostics.inspect_tools(NativeOptions(soffice="selected-soffice", timeout=7))
    assert error is None
    assert facts.capabilities["pdfua_link_descriptions"] == (
        "supported" if supported else "unsupported"
    )
    assert facts.toolchain.libreoffice == ToolIdentity("LibreOffice", "26.8")
    assert facts.toolchain.verapdf == ToolIdentity("veraPDF", "1.28")
    assert facts.schema_versions == ("1.3", "1.4")
    assert visited
    assert not visited[0].exists()
    output = capsys.readouterr()
    assert not output.out
    assert not output.err


def test_probe_failure_retains_identity_facts_and_controlled_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identities(monkeypatch)
    failure = ToolFailedError("named-link export failed", details="native diagnostic")

    def capability(_source: Path, _settings: ExportSettings) -> bool:
        raise failure

    monkeypatch.setattr(diagnostics, "link_descriptions_supported", capability)
    facts, error = diagnostics.inspect_tools()
    assert error is failure
    assert facts.toolchain.libreoffice == ToolIdentity("LibreOffice", "26.8")
    assert facts.capabilities["pdfua_link_descriptions"] is None


def test_missing_tools_have_no_identity_and_return_probe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = ToolNotFoundError("tool unavailable")

    def missing(*_args: object) -> str:
        raise failure

    def capability(_source: Path, _settings: ExportSettings) -> bool:
        raise failure

    monkeypatch.setattr(diagnostics, "find_soffice", missing)
    monkeypatch.setattr(diagnostics, "find_verapdf", missing)
    monkeypatch.setattr(diagnostics, "link_descriptions_supported", capability)
    facts, error = diagnostics.inspect_tools()
    assert facts.toolchain.libreoffice is None
    assert facts.toolchain.verapdf is None
    assert facts.capabilities["pdfua_link_descriptions"] is None
    assert error is failure


def test_unsupported_version_is_not_reported_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def unsupported(_requested: object) -> str:
        message = "LibreOffice 7.6 is unsupported"
        raise ToolFailedError(message)

    monkeypatch.setattr(diagnostics, "find_soffice", unsupported)
    with pytest.raises(ToolFailedError, match="unsupported"):
        diagnostics.inspect_tools()


def test_registry_without_probe_returns_partial_unsupported_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identities(monkeypatch)
    monkeypatch.setattr(REGISTRY[Family.TEXT], "link_probe", lambda _directory: None)
    facts, error = diagnostics.inspect_tools()
    assert isinstance(error, UnsupportedKindError)
    assert facts.capabilities["pdfua_link_descriptions"] is None
    assert facts.toolchain.libreoffice == ToolIdentity("LibreOffice", "26.8")
