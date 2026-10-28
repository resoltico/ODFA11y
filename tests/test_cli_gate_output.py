# SPDX-License-Identifier: MPL-2.0
"""Human command outcomes describe the actual gate and retain actionable evidence."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from odfa11y.cli import main
from odfa11y.cli import pipeline as cli_pipeline
from odfa11y.evidence import render_review
from odfa11y.outcomes import StageName, StageStatus
from odfa11y.pdf.fidelity import FidelityPolicy
from odfa11y.pipeline import RunRecord, StageResult
from odfa11y.pipeline.profiles import PROFILES
from odfa11y.records import DocumentIdentity
from odfa11y.report import Report, rules

from .fixtures import make_minimal_odt
from .record_fixtures import record
from .reviewed_plans import plan_header

if TYPE_CHECKING:
    from pathlib import Path


def test_strict_text_warning_has_one_authoritative_failed_outcome(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "warning.odt", features={"with_plain_email": True})
    assert main(["audit", str(source), "--strict"]) == 1
    output = capsys.readouterr()
    assert "Check: no errors" in output.out
    assert "Command: failed (exit 1; warnings rejected" in output.out
    assert "LINK001" in output.out
    assert "PASS" not in output.out
    assert not output.err


def test_partial_audit_ends_with_execution_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "clean.odt")
    assert main(["audit", str(source), str(tmp_path / "missing.odt")]) == 3
    output = capsys.readouterr()
    assert "Check: no errors" in output.out
    assert "Command: failed (exit 3; execution failure; checks may be incomplete)" in output.out
    assert "Cannot audit" in output.err


@pytest.mark.parametrize("output_format", ["text", "json"])
def test_production_warning_failure_preserves_findings_and_schema(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], output_format: str
) -> None:
    source = make_minimal_odt(tmp_path / "warning.odt", features={"with_plain_email": True})
    config = tmp_path / "plan.toml"
    config.write_text(plan_header(source) + "", encoding="utf-8")
    evidence = tmp_path / "evidence"
    assert (
        main([
            "pipeline",
            str(source),
            "--plan",
            str(config),
            "--output-dir",
            str(evidence),
            "--profile",
            "production",
            "--format",
            output_format,
        ])
        == 1
    )
    output = capsys.readouterr()
    stored = json.loads((evidence / "run.json").read_text(encoding="utf-8"))
    assert stored["failed_stage"] == "audit-remediated"
    assert stored["format"] == 3
    if output_format == "json":
        assert json.loads(output.out)["failed_stage"] == "audit-remediated"
    else:
        assert "Pipeline profile: production" in output.out
        assert "Command: failed (exit 1" in output.out
        assert "Gate findings: audit-remediated" in output.out
        assert "LINK001" in output.out
        assert "REVIEW.md" in output.out
    assert not output.err


def test_inspect_success_still_surfaces_warning_and_review_scope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "warning.odt", features={"with_plain_email": True})
    config = tmp_path / "plan.toml"
    config.write_text(plan_header(source) + "", encoding="utf-8")
    assert (
        main([
            "pipeline",
            str(source),
            "--plan",
            str(config),
            "--output-dir",
            str(tmp_path / "evidence"),
            "--profile",
            "inspect",
        ])
        == 0
    )
    output = capsys.readouterr().out
    assert "Command: completed (exit 0" in output
    assert "LINK001" in output
    assert "human review is still required" in output


@pytest.mark.parametrize("failure", ["validation failed", "executable unavailable"])
def test_review_does_not_claim_a_failed_validator_was_not_run(failure: str) -> None:
    data = record(status="failed", failed_stage="validate-pdf")
    data.profile = PROFILES["production"]
    data.stages[1] = replace(data.stages[1], status=StageStatus.FAILED, reason=failure)
    text = render_review(data)
    assert "Automated gates: **FAILED**" in text
    assert "Assurance profile: `production`" in text
    assert "veraPDF did not pass" in text
    assert "veraPDF did not run" not in text
    assert "Human review still required" in text


def test_pipeline_failure_shows_source_findings_and_safe_tool_details(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source = Report(kind="odf", subject="source.odt")
    source.add(rules.LINK001)
    data = RunRecord(
        document=DocumentIdentity("doc.odt"),
        operations=(),
        policy=FidelityPolicy(),
        profile=PROFILES["inspect"],
    )
    data.stages = [
        StageResult(StageName.AUDIT_SOURCE, StageStatus.PASSED, report=source, gate=False),
        StageResult(
            StageName.REMEDIATE,
            StageStatus.FAILED,
            "native tool failed",
            error=True,
            details="untrusted\x1b[31m\nCommand: completed",
        ),
    ]
    config = tmp_path / "plan.toml"
    config.write_text(plan_header(tmp_path / "source.odt") + "", encoding="utf-8")
    monkeypatch.setattr(cli_pipeline, "run_pipeline", lambda *_args, **_kwargs: data)
    assert main(["pipeline", "source.odt", "--plan", str(config), "--output-dir", "evidence"]) == 3
    text = capsys.readouterr().out
    assert "Before remediation: audit-source" in text
    assert "LINK001" in text
    assert "Command: failed (exit 3" in text
    assert "Tool details:" in text
    assert "\x1b" not in text
    assert "\nCommand: completed" not in text
