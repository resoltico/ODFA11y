# SPDX-License-Identifier: MPL-2.0
"""Exporter capability verdicts require positive/negative evidence and scoped identities."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
lazy from pathlib import Path

import pytest
from pypdf.generic import NameObject

from odfa11y.families import REGISTRY
from odfa11y.native.export import ExportSettings, find_soffice, identify_soffice
from odfa11y.native.probes import CapabilityStatus, ProbeCache, ProbeId
from odfa11y.native.process import ToolIdentity
from odfa11y.odf import OdfDocument, validate

from .probe_fixtures import fake_export, pdf_control

if TYPE_CHECKING:
    from collections.abc import Callable


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
    monkeypatch: pytest.MonkeyPatch, probe_id: ProbeId, *, supported: bool
) -> None:

    monkeypatch.setattr(
        "odfa11y.native.probe_pdf.validate_pdfua",
        lambda *_args, **_kwargs: SimpleNamespace(compliant=True),
    )
    execution = ProbeCache().run(
        PROBES[probe_id],
        ToolIdentity("LibreOffice", "26.8.1.1"),
        ExportSettings(PROBES[probe_id].export_filter),
        export=fake_export(probe_id, supported=supported),
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

    result = ProbeCache().run(
        PROBES[ProbeId.LINK_DESCRIPTIONS],
        ToolIdentity("LibreOffice", "26.8.1.1"),
        ExportSettings("writer_pdf_Export"),
        export=export,
    )
    assert result.error is None
    assert result.result.status == CapabilityStatus.UNSUPPORTED


@pytest.mark.integration
@pytest.mark.parametrize("probe_id", list(ProbeId))
def test_each_native_probe_produces_a_scoped_observation(
    probe_id: ProbeId, external_tool: Callable[..., str]
) -> None:
    executable = find_soffice(external_tool("soffice", "libreoffice"))
    identity = identify_soffice(executable)
    execution = ProbeCache().run(
        PROBES[probe_id],
        identity,
        ExportSettings(PROBES[probe_id].export_filter, executable),
        verapdf_path=external_tool("verapdf"),
    )
    assert execution.error is None, execution.error
    assert execution.result.status in {CapabilityStatus.SUPPORTED, CapabilityStatus.UNSUPPORTED}
    assert execution.result.id == probe_id
    assert execution.result.family == PROBES[probe_id].family
    assert execution.result.tool == identity


def test_calc_support_requires_independent_validator_acceptance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "odfa11y.native.probe_pdf.validate_pdfua",
        lambda *_args, **_kwargs: SimpleNamespace(compliant=False),
    )
    execution = ProbeCache().run(
        PROBES[ProbeId.CALC_PDFUA],
        ToolIdentity("LibreOffice", "26.8.1.1"),
        ExportSettings("calc_pdf_Export"),
        export=fake_export(ProbeId.CALC_PDFUA, supported=True),
    )
    assert execution.error is None
    assert execution.result.status == CapabilityStatus.UNSUPPORTED
