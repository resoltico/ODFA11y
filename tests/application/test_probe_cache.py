# SPDX-License-Identifier: MPL-2.0
"""A batch reuses relevant native observations without leaking identity or failure state."""

from __future__ import annotations

import json
from dataclasses import replace
lazy from pathlib import Path

lazy import pytest

from odfa11y.batch import run_batch
from odfa11y.content import document_links, link_fingerprint
from odfa11y.errors import ToolFailedError
from odfa11y.families.text.probes import PROBES
from odfa11y.native.export import ExportSettings
from odfa11y.native.probes import CapabilityStatus, ProbeCache, ProbeId
from odfa11y.native.process import ToolIdentity
from odfa11y.odf import OdfDocument, PackageStorage
from odfa11y.pipeline.context import RunSettings
from tests.batch.test_batch import manifest_file
from tests.fixtures.pdf import tagged_writer
from tests.fixtures.plans import plan_header
from tests.fixtures.probes import fake_export
from tests.fixtures.writer import make_minimal_odt

LINK = next(p for p in PROBES if p.id == ProbeId.LINK_DESCRIPTIONS)


def test_cache_keys_include_tool_identity_and_selected_executable() -> None:
    calls = []
    control = fake_export(ProbeId.LINK_DESCRIPTIONS, supported=True)

    def export(source: Path, destination: Path, settings: ExportSettings) -> Path:
        calls.append(settings.soffice)
        return control(source, destination, settings)

    cache = ProbeCache()
    first = cache.run(
        LINK,
        ToolIdentity("LibreOffice", "26.8.1.1"),
        ExportSettings("writer_pdf_Export", "first"),
        export=export,
    )
    repeated = cache.run(
        LINK,
        ToolIdentity("LibreOffice", "26.8.1.1"),
        ExportSettings("writer_pdf_Export", "first"),
        export=export,
    )
    assert first.result is repeated.result
    assert calls == ["first"]
    cache.run(
        LINK,
        ToolIdentity("LibreOffice", "26.8.2.1"),
        ExportSettings("writer_pdf_Export", "first"),
        export=export,
    )
    cache.run(
        LINK,
        ToolIdentity("LibreOffice", "26.8.2.1"),
        ExportSettings("writer_pdf_Export", "second"),
        export=export,
    )
    assert calls == ["first", "first", "second"]


def test_indeterminate_failure_is_not_reused_as_a_conclusive_verdict() -> None:
    calls = 0
    control = fake_export(ProbeId.LINK_DESCRIPTIONS, supported=True)

    def export(source: Path, destination: Path, settings: ExportSettings) -> Path:
        nonlocal calls
        calls += 1
        if calls == 1:
            message = "Controlled transient failure"
            raise ToolFailedError(message)
        return control(source, destination, settings)

    cache = ProbeCache()
    identity = ToolIdentity("LibreOffice", "26.8.1.1")
    settings = ExportSettings("writer_pdf_Export", "selected")
    failed = cache.run(LINK, identity, settings, export=export)
    assert failed.result.status == CapabilityStatus.NOT_TESTED
    assert failed.error is not None
    passed = cache.run(LINK, identity, settings, export=export)
    assert passed.result.status == CapabilityStatus.SUPPORTED
    assert passed.error is None
    assert calls == 2


def test_batch_of_text_items_runs_relevant_link_probe_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    storage = PackageStorage(source)
    storage.write_member(
        "content.xml",
        storage.read("content.xml").replace(
            b"Body paragraph.",
            b'See <text:a xlink:type="simple" xlink:href="https://example.test/a">'
            b"the guide</text:a>.",
        ),
    )
    storage.save(source)
    document = OdfDocument.open(source)
    fingerprint = link_fingerprint(document, document_links(document)[0])
    plan = tmp_path / "review.plan.toml"
    plan.write_text(
        plan_header(source)
        + '[decisions."link.description"."content/link[1]"]\ndescription = "Reviewed guide"\n'
        + f'fingerprint = "{fingerprint}"\n'
    )
    manifest = manifest_file(
        tmp_path, [(name, "source.odt", plan.name) for name in ["one", "two", "three"]]
    )
    monkeypatch.setattr("odfa11y.pipeline.engine.find_soffice", lambda _: "controlled-soffice")
    monkeypatch.setattr(
        "odfa11y.pipeline.engine.identify_soffice",
        lambda _: ToolIdentity("LibreOffice", "26.8.1.1"),
    )
    control = fake_export(ProbeId.LINK_DESCRIPTIONS, supported=True)

    def document_export(_source: Path, destination: Path, _settings: ExportSettings) -> Path:
        tagged_writer(["H1", "P"]).write(destination)
        return destination

    monkeypatch.setattr("odfa11y.pipeline.engine.export_pdfua", document_export)
    calls = []

    def probe_export(source: Path, destination: Path, settings: ExportSettings) -> Path:
        calls.append(source.name)
        return control(source, destination, settings)

    monkeypatch.setattr("odfa11y.native.probes.export_pdfua", probe_export)
    result = run_batch(manifest, tmp_path / "out", RunSettings())
    assert result.exit_status == 0, result.as_dict()
    assert calls == ["link.odt"]
    repeated_batch = run_batch(manifest, tmp_path / "second-out", RunSettings())
    assert repeated_batch.exit_status == 0, repeated_batch.as_dict()
    assert calls == ["link.odt", "link.odt"]
    for name in ["one", "two", "three"]:
        record = json.loads((tmp_path / "out" / name / "run.json").read_text())
        observations = record["toolchain"]["capabilities"]
        assert len(observations) == 1
        assert observations[0]["id"] == "link-descriptions"
        assert observations[0]["status"] == "supported"


def test_changed_probe_definition_cannot_reuse_an_old_verdict() -> None:
    cache = ProbeCache()
    identity = ToolIdentity("LibreOffice", "26.8.1.1")
    settings = ExportSettings("writer_pdf_Export", "selected")
    export = fake_export(ProbeId.LINK_DESCRIPTIONS, supported=True)
    assert (
        cache.run(LINK, identity, settings, export=export).result.status
        == CapabilityStatus.SUPPORTED
    )
    altered = replace(LINK, evaluate=lambda *_args: False)
    assert (
        cache.run(altered, identity, settings, export=export).result.status
        == CapabilityStatus.UNSUPPORTED
    )
