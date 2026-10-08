# SPDX-License-Identifier: MPL-2.0
"""Required validator absence is execution failure at its actual pipeline boundary."""

from __future__ import annotations

import importlib
import json
from typing import TYPE_CHECKING

import pytest

from odfa11y.cli import main
from odfa11y.evidence import check_bundle
from odfa11y.external_tools import ToolIdentity
from odfa11y.fidelity import FidelityPolicy
from odfa11y.pipeline import PipelineOptions, run_pipeline

from .fixtures import make_minimal_odt
from .pdf_fixtures import tagged_writer
from .test_batch import manifest_file

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.fixture
def successful_exports(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = importlib.import_module("odfa11y.pipeline.run")
    monkeypatch.setattr(runner, "find_soffice", lambda _requested: "soffice")
    monkeypatch.setattr(
        runner, "identify_soffice", lambda _path: ToolIdentity("LibreOffice", "26.8.0.3")
    )
    monkeypatch.setattr(runner, "link_descriptions_supported", lambda *_args: True)

    def export(_source: Path, destination: Path, _settings: object) -> Path:
        tagged_writer(["H1"]).write(destination)
        return destination

    monkeypatch.setattr(runner, "export_pdfua", export)


@pytest.mark.usefixtures("successful_exports")
def test_required_validator_failure_reaches_stage_and_retains_evidence(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    target = tmp_path / "evidence"
    result = run_pipeline(
        source,
        [],
        FidelityPolicy(),
        target,
        PipelineOptions(profile="production", verapdf_path=str(tmp_path / "missing-verapdf")),
    )
    assert result.failed_stage == "verapdf"
    assert result.exit_status == 3
    assert all(stage.status == "passed" for stage in result.stages[:7])
    assert result.stages[-1].status == "skipped"
    assert result.stages[-1].reason == "not run: verapdf failed"
    assert check_bundle(target) == []
    assert json.loads((target / "run.json").read_text())["status"] == "failed"


@pytest.mark.usefixtures("successful_exports")
def test_cli_and_batch_keep_required_validator_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    plan = tmp_path / "plan.toml"
    plan.write_text('[document]\ntitle="T"\nlanguage="en-GB"')
    missing = str(tmp_path / "missing-verapdf")
    assert (
        main([
            "pipeline",
            str(source),
            "--config",
            str(plan),
            "--output-dir",
            str(tmp_path / "single"),
            "--profile",
            "production",
            "--verapdf-path",
            missing,
        ])
        == 3
    )
    manifest = manifest_file(
        tmp_path, [("first", "source.odt", "plan.toml"), ("second", "source.odt", "plan.toml")]
    )
    assert (
        main([
            "batch",
            str(manifest),
            "--output-dir",
            str(tmp_path / "batch"),
            "--profile",
            "production",
            "--verapdf-path",
            missing,
        ])
        == 3
    )
    record = json.loads((tmp_path / "batch" / "batch.json").read_text())
    assert [item["exit_status"] for item in record["items"]] == [3, 3]
    assert [item["failed_stage"] for item in record["items"]] == ["verapdf", "verapdf"]
    for name in ("first", "second"):
        assert check_bundle(tmp_path / "batch" / name) == []
    assert "Traceback" not in capsys.readouterr().err


def test_optional_audit_validation_keeps_warning_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf = tmp_path / "source.pdf"
    tagged_writer(["H1"]).write(pdf)
    args = ["audit", str(pdf), "--verapdf-path", str(tmp_path / "missing-verapdf")]
    assert main(args) == 0
    assert main([*args, "--strict"]) == 1
    assert "VERA000" in capsys.readouterr().out


@pytest.mark.integration
def test_real_production_reaches_missing_required_validator(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    target = tmp_path / "evidence"
    record = run_pipeline(
        source,
        [],
        FidelityPolicy(),
        target,
        PipelineOptions(
            profile="production",
            soffice=external_tool("soffice", "libreoffice"),
            verapdf_path=str(tmp_path / "missing-verapdf"),
        ),
    )
    assert all(stage.status == "passed" for stage in record.stages[:7]), record.as_dict()
    assert record.failed_stage == "verapdf"
    assert record.exit_status == 3
    assert check_bundle(target) == []
