# SPDX-License-Identifier: MPL-2.0
"""Core tool inspection returns facts and probe failures without rendering a UI."""

import importlib
from dataclasses import replace
lazy from pathlib import Path

import pytest

from odfa11y.application.native import NativeTools
from odfa11y.application.tools import Tools
from odfa11y.errors import ToolFailure, ToolUnavailable
from odfa11y.families import REGISTRY
from odfa11y.families.probes import CapabilityStatus, ProbeId
from odfa11y.odf import OdfDocument
from odfa11y.tool_identity import ToolIdentity
from tests.fixtures.native import validation_result
from tests.fixtures.probes import fake_export
from tests.fixtures.schema import assert_record_schema
lazy from odfa11y.native.libreoffice import ExportSettings

diagnostics = importlib.import_module("odfa11y.application.doctor")


def identities(native_tools: NativeTools) -> NativeTools:
    native_tools = replace(native_tools, locate=lambda requested: requested or "soffice")
    native_tools = replace(native_tools, validator=lambda _requested=None: "verapdf")
    native_tools = replace(
        native_tools, identify=lambda _executable, **_options: ToolIdentity("LibreOffice", "26.8")
    )
    native_tools = replace(
        native_tools, identify_validator=lambda *_args, **_options: ToolIdentity("veraPDF", "1.28")
    )
    return native_tools


@pytest.mark.parametrize("supported", [False, True])
def test_core_inspection_uses_real_registered_probe_and_returns_no_ui(
    native_tools: NativeTools,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    supported: bool,
) -> None:
    native_tools = identities(native_tools)
    visited: list[Path] = []

    def exporter(source: Path, destination: Path, settings: ExportSettings) -> Path:
        visited.append(source)
        document = OdfDocument.open(source)
        assert document.kind is not None
        assert settings.office.executable == "selected-soffice"
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

    native_tools = replace(native_tools, export=exporter)
    native_tools = replace(native_tools, validate=lambda *_args, **_kwargs: validation_result(True))
    facts = diagnostics.doctor(
        tools=Tools(soffice="selected-soffice", timeout=7), native_tools=native_tools
    )
    assert_record_schema(facts)
    assert facts.error is None
    assert len(facts.capabilities) == len(ProbeId)
    assert all(
        result.status == (CapabilityStatus.SUPPORTED if supported else CapabilityStatus.UNSUPPORTED)
        for result in facts.capabilities
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
    native_tools: NativeTools,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native_tools = identities(native_tools)
    failure = ToolFailure("named-link export failed", details="native diagnostic")

    def exporter(_source: Path, _destination: Path, _settings: ExportSettings) -> Path:
        raise failure

    native_tools = replace(native_tools, export=exporter)
    facts = diagnostics.doctor(native_tools=native_tools)
    assert facts.error is failure
    assert facts.toolchain.libreoffice == ToolIdentity("LibreOffice", "26.8")
    assert all(result.status == CapabilityStatus.NOT_TESTED for result in facts.capabilities)


def test_missing_tools_have_no_identity_and_return_probe_error(
    native_tools: NativeTools,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = ToolUnavailable("tool unavailable")

    def missing(*_args: object) -> str:
        raise failure

    def exporter(_source: Path, _destination: Path, _settings: ExportSettings) -> Path:
        raise failure

    native_tools = replace(native_tools, locate=missing)
    native_tools = replace(native_tools, validator=missing)
    native_tools = replace(native_tools, export=exporter)
    facts = diagnostics.doctor(native_tools=native_tools)
    assert facts.toolchain.libreoffice is None
    assert facts.toolchain.verapdf is None
    assert all(result.status == CapabilityStatus.NOT_TESTED for result in facts.capabilities)
    assert facts.error is failure


def test_unsupported_version_is_not_reported_as_missing(
    native_tools: NativeTools, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unsupported(_requested: object) -> str:
        message = "LibreOffice 7.6 is unsupported"
        raise ToolFailure(message)

    native_tools = replace(native_tools, locate=unsupported)
    facts = diagnostics.doctor(native_tools=native_tools)
    assert facts.error is not None
    assert "unsupported" in facts.error.message
    assert all("unsupported" in (result.reason or "") for result in facts.capabilities)


def test_registry_without_any_probes_returns_partial_unsupported_error(
    native_tools: NativeTools,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native_tools = identities(native_tools)
    for family, spec in tuple(REGISTRY.items()):
        monkeypatch.setitem(REGISTRY, family, replace(spec, probes=()))
    facts = diagnostics.doctor(native_tools=native_tools)
    assert facts.error is None
    assert facts.capabilities == ()
    assert all(result.status == CapabilityStatus.NOT_TESTED for result in facts.capabilities)
    assert facts.toolchain.libreoffice == ToolIdentity("LibreOffice", "26.8")


def test_doctor_without_verapdf_leaves_calc_explicitly_unmeasured(
    native_tools: NativeTools,
) -> None:
    native_tools = identities(native_tools)

    def missing(_requested):
        message = "veraPDF unavailable"
        raise ToolUnavailable(message)

    native_tools = replace(native_tools, validator=missing)
    facts = diagnostics.doctor(native_tools=native_tools)
    calc = next(result for result in facts.capabilities if result.id is ProbeId.CALC_PDFUA)
    assert calc.status is CapabilityStatus.NOT_TESTED
    assert calc.reason == "veraPDF unavailable"
    assert calc.related_rules
    assert calc.meaning == ProbeId.CALC_PDFUA.meaning
    assert facts.exit_status == 0
