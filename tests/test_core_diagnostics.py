# SPDX-License-Identifier: MPL-2.0
"""Core tool inspection returns facts and probe failures without rendering a UI."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from odfa11y.errors import ToolFailedError, ToolNotFoundError, UnsupportedKindError
from odfa11y.families import REGISTRY
from odfa11y.native.probes import CapabilityStatus, ProbeId
from odfa11y.native.process import ToolIdentity
from odfa11y.odf import OdfDocument
from odfa11y.pipeline import diagnostics
from odfa11y.tools import Tools

from .probe_fixtures import fake_export

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.native.export import ExportSettings


def identities(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostics, "find_soffice", lambda requested: requested or "soffice")
    monkeypatch.setattr(diagnostics, "find_verapdf", lambda _requested=None: "verapdf")
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

    def exporter(source: Path, destination: Path, settings: ExportSettings) -> Path:
        visited.append(source)
        document = OdfDocument.open(source)
        assert document.kind is not None
        assert settings.soffice == "selected-soffice"
        assert settings.timeout == 7
        by_source = {
            "link.odt": ProbeId.LINK_DESCRIPTIONS,
            "decorative.odt": ProbeId.DECORATIVE_ROLE,
            "columns.odt": ProbeId.WRITER_HEADER_COLUMNS,
            "expression.odf": ProbeId.MATH_TAGGING,
            "table.ods": ProbeId.CALC_PDFUA,
        }
        return fake_export(by_source[source.name], supported=supported)(
            source, destination, settings
        )

    monkeypatch.setattr("odfa11y.native.probes.export_pdfua", exporter)
    monkeypatch.setattr(
        "odfa11y.native.probe_pdf.validate_pdfua",
        lambda *_args, **_kwargs: SimpleNamespace(compliant=True),
    )
    facts, error = diagnostics.inspect_tools(Tools(soffice="selected-soffice", timeout=7))
    assert error is None
    assert len(facts.toolchain.capabilities) == len(ProbeId)
    assert all(
        result.status == (CapabilityStatus.SUPPORTED if supported else CapabilityStatus.UNSUPPORTED)
        for result in facts.toolchain.capabilities
    )
    assert facts.toolchain.libreoffice == ToolIdentity("LibreOffice", "26.8")
    assert facts.toolchain.verapdf == ToolIdentity("veraPDF", "1.28")
    assert facts.schema_versions == ("1.3", "1.4")
    assert len(visited) == len(ProbeId)
    assert all(not path.exists() for path in visited)
    output = capsys.readouterr()
    assert not output.out
    assert not output.err


def test_probe_failure_retains_identity_facts_and_controlled_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identities(monkeypatch)
    failure = ToolFailedError("named-link export failed", details="native diagnostic")

    def exporter(_source: Path, _destination: Path, _settings: ExportSettings) -> Path:
        raise failure

    monkeypatch.setattr("odfa11y.native.probes.export_pdfua", exporter)
    facts, error = diagnostics.inspect_tools()
    assert error is failure
    assert facts.toolchain.libreoffice == ToolIdentity("LibreOffice", "26.8")
    assert all(
        result.status == CapabilityStatus.NOT_TESTED for result in facts.toolchain.capabilities
    )


def test_missing_tools_have_no_identity_and_return_probe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = ToolNotFoundError("tool unavailable")

    def missing(*_args: object) -> str:
        raise failure

    def exporter(_source: Path, _destination: Path, _settings: ExportSettings) -> Path:
        raise failure

    monkeypatch.setattr(diagnostics, "find_soffice", missing)
    monkeypatch.setattr(diagnostics, "find_verapdf", missing)
    monkeypatch.setattr("odfa11y.native.probes.export_pdfua", exporter)
    facts, error = diagnostics.inspect_tools()
    assert facts.toolchain.libreoffice is None
    assert facts.toolchain.verapdf is None
    assert all(
        result.status == CapabilityStatus.NOT_TESTED for result in facts.toolchain.capabilities
    )
    assert error is failure


def test_unsupported_version_is_not_reported_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def unsupported(_requested: object) -> str:
        message = "LibreOffice 7.6 is unsupported"
        raise ToolFailedError(message)

    monkeypatch.setattr(diagnostics, "find_soffice", unsupported)
    with pytest.raises(ToolFailedError, match="unsupported"):
        diagnostics.inspect_tools()


def test_registry_without_any_probes_returns_partial_unsupported_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identities(monkeypatch)
    for adapter in REGISTRY.values():
        monkeypatch.setattr(adapter, "probes", ())
    facts, error = diagnostics.inspect_tools()
    assert isinstance(error, UnsupportedKindError)
    assert all(
        result.status == CapabilityStatus.NOT_TESTED for result in facts.toolchain.capabilities
    )
    assert facts.toolchain.libreoffice == ToolIdentity("LibreOffice", "26.8")
