# SPDX-License-Identifier: AGPL-3.0-only
"""Exporter capability verdicts require positive/negative evidence and scoped identities."""

from dataclasses import replace
lazy from pathlib import Path

import pytest
from pypdf.generic import NameObject

from odfa11y.application.native import NativeTools
from odfa11y.errors import ToolFailure
from odfa11y.families import REGISTRY
from odfa11y.families.probes import CapabilityStatus, ProbeId, measure_probe
from odfa11y.native.libreoffice import ExportSettings
from odfa11y.odf import OdfDocument, validate
from odfa11y.tool_identity import ToolIdentity
from tests.fixtures.native import export_settings, validation_result, validator_tool
from tests.fixtures.probes import fake_export, pdf_control

PROBES = {probe.id: probe for adapter in REGISTRY.values() for probe in adapter.probes}


@pytest.mark.parametrize("probe_id", list(ProbeId))
def test_each_declared_source_is_schema_valid(tmp_path: Path, probe_id: ProbeId) -> None:
    source = PROBES[probe_id].source_writer(tmp_path)
    result = validate(OdfDocument.open(source))
    assert result.available
    assert result.count == 0, result.messages()


@pytest.mark.parametrize("probe_id", list(ProbeId))
@pytest.mark.parametrize("supported", [True, False])
def test_positive_and_negative_exporter_controls(
    native_tools: NativeTools,
    monkeypatch: pytest.MonkeyPatch,
    probe_id: ProbeId,
    *,
    supported: bool,
) -> None:

    native_tools = replace(native_tools, validate=lambda *_args, **_kwargs: validation_result(True))
    execution = measure_probe(
        PROBES[probe_id],
        ToolIdentity("LibreOffice", "26.8.1.1"),
        export_settings(PROBES[probe_id].export_filter),
        export=fake_export(probe_id, supported=supported),
        validate=native_tools.validate,
        verapdf=validator_tool(),
    )
    assert execution.error is None
    assert execution.result.status == (
        CapabilityStatus.SUPPORTED if supported else CapabilityStatus.UNSUPPORTED
    )
    assert execution.result.tool == ToolIdentity("LibreOffice", "26.8.1.1")


def test_untagged_link_export_cannot_report_support() -> None:

    def export(_source: Path, destination: Path, _settings: ExportSettings) -> Path:
        writer = pdf_control(ProbeId.LINK_DESCRIPTIONS, supported=True)
        writer.root_object.pop(NameObject("/StructTreeRoot"), None)
        writer.root_object.pop(NameObject("/MarkInfo"), None)
        writer.write(destination)
        return destination

    result = measure_probe(
        PROBES[ProbeId.LINK_DESCRIPTIONS],
        ToolIdentity("LibreOffice", "26.8.1.1"),
        export_settings("writer_pdf_Export"),
        export=export,
    )
    assert result.error is None
    assert result.result.status == CapabilityStatus.UNSUPPORTED


def test_calc_support_requires_independent_validator_acceptance(
    native_tools: NativeTools,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native_tools = replace(
        native_tools, validate=lambda *_args, **_kwargs: validation_result(False)
    )
    execution = measure_probe(
        PROBES[ProbeId.CALC_PDFUA],
        ToolIdentity("LibreOffice", "26.8.1.1"),
        export_settings("calc_pdf_Export"),
        export=fake_export(ProbeId.CALC_PDFUA, supported=True),
        validate=native_tools.validate,
        verapdf=validator_tool(),
    )
    assert execution.error is None
    assert execution.result.status == CapabilityStatus.UNSUPPORTED


def test_repeating_an_experiment_after_failure_measures_again() -> None:
    calls = []
    probe = PROBES[ProbeId.LINK_DESCRIPTIONS]
    control = fake_export(probe.id, supported=True)

    def transient(source, destination, settings):
        calls.append(source)
        if len(calls) == 1:
            message = "Transient controlled export failure"
            raise ToolFailure(message)
        return control(source, destination, settings)

    identity = ToolIdentity("LibreOffice", "26.8.0.3")
    settings = export_settings(probe.export_filter, "selected-office")
    failed = measure_probe(probe, identity, settings, export=transient)
    repeated = measure_probe(probe, identity, settings, export=transient)
    assert failed.result.status is CapabilityStatus.NOT_TESTED
    assert failed.error is not None
    assert repeated.result.status is CapabilityStatus.SUPPORTED
    assert repeated.error is None
    assert len(calls) == 2
