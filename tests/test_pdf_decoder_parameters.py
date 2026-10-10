# SPDX-License-Identifier: MPL-2.0
"""Malformed decoder parameters refuse at the real written/read PDF boundary."""

from __future__ import annotations

import importlib
import json
from typing import TYPE_CHECKING

import pytest
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from odfa11y.batch import run_batch
from odfa11y.cli import main
from odfa11y.errors import ToolFailedError
from odfa11y.evidence import check_bundle
from odfa11y.external_tools import ToolIdentity
from odfa11y.fidelity import FidelityPolicy, compare_pdfs
from odfa11y.pdf import audit_pdfua
from odfa11y.pipeline import PipelineOptions

from .fixtures import make_minimal_odt
from .pdf_fixtures import register, tagged_writer

if TYPE_CHECKING:
    from pathlib import Path

    from odfa11y.pdf import ExportSettings


def predictor_pdf(path: Path, predictor: object) -> Path:
    """Write a Flate stream with an independently selected predictor parameter.

    Returns
    -------
    Path
        The written PDF.

    """
    writer = tagged_writer()
    data = DecodedStreamObject()
    data.set_data(b"\x00 " if predictor == NumberObject(10) else b" ")
    encoded = data.flate_encode()
    encoded[NameObject("/DecodeParms")] = DictionaryObject({NameObject("/Predictor"): predictor})
    writer.pages[0][NameObject("/Contents")] = register(writer, encoded)
    writer.write(path)
    return path


def test_invalid_predictor_refuses_and_retains_mixed_audits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    good = predictor_pdf(tmp_path / "good.pdf", NumberObject(1))
    bad = predictor_pdf(tmp_path / "bad.pdf", NameObject("/Bad"))
    before = bad.read_bytes()
    report = audit_pdfua(bad)
    assert [f.rule_id for f in report.findings] == ["PDF000"]
    assert "Malformed PDF stream decoding parameters" in report.findings[0].message
    with pytest.raises(ToolFailedError, match="Malformed PDF stream decoding parameters"):
        compare_pdfs(good, bad, FidelityPolicy())
    assert main(["audit", str(good), str(bad), str(good), "--format", "json"]) == 2
    output = capsys.readouterr()
    assert not output.err
    reports = json.loads(output.out)
    assert len(reports) == 3
    assert all(f["rule_id"] != "PDF000" for r in (reports[0], reports[2]) for f in r["findings"])
    assert [f["rule_id"] for f in reports[1]["findings"]] == ["PDF000"]
    assert main(["compare", str(good), str(bad)]) == 3
    output = capsys.readouterr()
    assert "Traceback" not in output.err
    assert "Malformed PDF stream decoding parameters" in output.err
    assert bad.read_bytes() == before


@pytest.mark.parametrize("predictor", [1, 10])
def test_supported_flate_predictors_remain_inspectable(tmp_path: Path, predictor: int) -> None:
    path = predictor_pdf(tmp_path / "flate.pdf", NumberObject(predictor))
    assert not any(f.rule_id == "PDF000" for f in audit_pdfua(path).findings)


def test_bad_exported_predictor_keeps_batch_failure_evidence_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    before = source.read_bytes()
    bad = predictor_pdf(tmp_path / "bad.pdf", NameObject("/Bad"))
    good = tmp_path / "good.pdf"
    tagged_writer().write(good)
    (tmp_path / "plan.toml").write_text("")
    manifest = tmp_path / "batch.toml"
    manifest.write_text(
        "\n".join(
            f'[[documents]]\nid = "{identity}"\nsource = "source.odt"\nplan = "plan.toml"\n'
            for identity in ("refused", "healthy")
        )
    )
    calls = 0

    def export(_source: Path, destination: Path, _settings: ExportSettings) -> Path:
        nonlocal calls
        calls += 1
        destination.write_bytes((bad if calls <= 2 else good).read_bytes())
        return destination

    runner = importlib.import_module("odfa11y.pipeline.run")
    monkeypatch.setattr(runner, "find_soffice", lambda _: "synthetic-exporter")
    monkeypatch.setattr(
        runner,
        "identify_soffice",
        lambda _: ToolIdentity("LibreOffice", "26.8.0.3"),
    )
    monkeypatch.setattr(runner, "link_descriptions_supported", lambda *_args: True)
    monkeypatch.setattr(runner, "export_pdfua", export)
    result = run_batch(manifest, tmp_path / "out", PipelineOptions())
    assert [item["exit_status"] for item in result.items] == [2, 0]
    assert result.items[0]["failed_stage"] == "audit-pdf"
    assert result.items[1]["status"] == "completed"
    bundle = tmp_path / "out" / "refused"
    record = json.loads((bundle / "run.json").read_text())
    audit = next(stage for stage in record["stages"] if stage["name"] == "audit-pdf")
    assert [f["rule_id"] for f in audit["report"]["findings"]] == ["PDF000"]
    assert all(
        stage["status"] == "skipped"
        for stage in record["stages"]
        if stage["name"] in {"verapdf", "fidelity"}
    )
    assert (bundle / "remediated.pdf").read_bytes() == bad.read_bytes()
    assert all(check_bundle(tmp_path / "out" / item["id"]) == [] for item in result.items)
    assert source.read_bytes() == before
