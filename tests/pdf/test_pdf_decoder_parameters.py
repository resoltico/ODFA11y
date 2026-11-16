# SPDX-License-Identifier: MPL-2.0
"""Malformed decoder parameters refuse at the real written/read PDF boundary."""

import json
from dataclasses import replace
lazy from pathlib import Path

import pytest
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from odfa11y.application.native import NativeTools
from odfa11y.cli import main
from odfa11y.errors import ToolFailure
from odfa11y.evidence import check_bundle
from odfa11y.families import probes as probe_operations
from odfa11y.pdf import audit_pdfua
from odfa11y.pdf.fidelity import compare_pdfs
from odfa11y.plans.fidelity import Pagination
from odfa11y.rules import registry as rules
from odfa11y.tool_identity import ToolIdentity
from tests.fixtures.pdf import register, tagged_writer
from tests.fixtures.plans import plan_header
from tests.fixtures.probes import conclusive_probe
from tests.fixtures.runs import RunSettings, run_batch
from tests.fixtures.writer import make_minimal_odt
lazy from odfa11y.native.libreoffice import ExportSettings


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
    assert [f.rule_id for f in report.findings] == [rules.PDF001.id]
    assert "Malformed PDF stream decoding parameters" in report.findings[0].message
    with pytest.raises(ToolFailure, match="Malformed PDF stream decoding parameters"):
        compare_pdfs(good, bad, Pagination.SAME())
    assert main(["audit", str(good), str(bad), str(good), "--format", "json"]) == 2
    output = capsys.readouterr()
    assert not output.err
    payload = json.loads(output.out)
    assert payload["exit_status"] == 2
    reports = [report for item in payload["inputs"] for report in item["reports"]]
    assert len(reports) == 3
    assert all(
        f["rule_id"] != rules.PDF001.id for r in (reports[0], reports[2]) for f in r["findings"]
    )
    assert [f["rule_id"] for f in reports[1]["findings"]] == [rules.PDF001.id]
    assert main(["compare", str(good), str(bad)]) == 3
    output = capsys.readouterr()
    assert "Traceback" not in output.err
    assert "Malformed PDF stream decoding parameters" in output.err
    assert bad.read_bytes() == before


@pytest.mark.parametrize("predictor", [1, 10])
def test_supported_flate_predictors_remain_inspectable(tmp_path: Path, predictor: int) -> None:
    path = predictor_pdf(tmp_path / "flate.pdf", NumberObject(predictor))
    assert not any(f.rule_id == rules.PDF001.id for f in audit_pdfua(path).findings)


def test_bad_exported_predictor_keeps_batch_failure_evidence_and_continues(
    native_tools: NativeTools, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    before = source.read_bytes()
    bad = predictor_pdf(tmp_path / "bad.pdf", NameObject("/Bad"))
    good = tmp_path / "good.pdf"
    tagged_writer().write(good)
    (tmp_path / "plan.toml").write_text(plan_header(source))
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

    native_tools = replace(native_tools, locate=lambda _: "synthetic-exporter")
    native_tools = replace(
        native_tools, identify=lambda _, **_options: ToolIdentity("LibreOffice", "26.8.0.3")
    )
    monkeypatch.setattr(probe_operations, "measure_probe", conclusive_probe)
    native_tools = replace(native_tools, export=export)
    result = run_batch(manifest, tmp_path / "out", RunSettings(), native_tools=native_tools)
    assert [item.exit_status for item in result.items] == [3, 0]
    assert result.items[0].failed_stage == "audit-pdf"
    assert result.items[1].status == "completed"
    bundle = tmp_path / "out" / "refused"
    record = json.loads((bundle / "run.json").read_text())
    audit = next(stage for stage in record["stages"] if stage["name"] == "audit-pdf")
    assert [f["rule_id"] for f in audit["outcome"]["report"]["findings"]] == [rules.PDF001.id]
    fidelity = next(stage for stage in record["stages"] if stage["name"] == "fidelity")
    assert fidelity["outcome"]["status"] == "crashed"

    assert (bundle / "remediated.pdf").read_bytes() == bad.read_bytes()
    assert all(check_bundle(tmp_path / "out" / item.id) == [] for item in result.items)
    assert source.read_bytes() == before
