# SPDX-License-Identifier: MPL-2.0
"""Human command outcomes describe the actual gate and retain actionable evidence."""

import json
from dataclasses import replace
lazy from pathlib import Path

import pytest

from odfa11y.cli import commands as cli_pipeline
from odfa11y.cli import main
from odfa11y.errors import DocumentRefusal, ToolFailure
from odfa11y.plans.fidelity import Pagination
from odfa11y.progress import Stage
from odfa11y.report import Report
from odfa11y.report.model import ReportKind
from odfa11y.rules import registry as rules
from odfa11y.run.record import DocumentIdentity, RunRecord, StageResult
from odfa11y.run.review import render_review
from odfa11y.status import Crashed, Passed, Profile, Refused
from tests.fixtures.plans import plan_header
from tests.fixtures.records import record
from tests.fixtures.writer import make_minimal_odt


def test_strict_text_warning_has_one_authoritative_failed_outcome(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "warning.odt", features={"with_plain_email": True})
    assert main(["audit", str(source), "--strict"]) == 1
    output = capsys.readouterr()
    assert "Findings: 0 error(s)" in output.out
    assert "Result: failed (exit 1)" in output.out
    assert rules.LINK001.id in output.out
    assert "PASS" not in output.out
    assert not output.err


def test_partial_audit_ends_with_execution_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "clean.odt")
    assert main(["audit", str(source), str(tmp_path / "missing.odt")]) == 3
    output = capsys.readouterr()
    assert "Findings: 0 error(s)" in output.out
    assert "Result: failed (exit 3)" in output.out
    assert "Cannot audit" in output.err


@pytest.mark.parametrize("output_format", ["text", "json"])
def test_production_warning_failure_preserves_findings_and_schema(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], output_format: str, native_tools
) -> None:
    source = make_minimal_odt(tmp_path / "warning.odt", features={"with_plain_email": True})
    config = tmp_path / "plan.toml"
    config.write_text(plan_header(source) + "", encoding="utf-8")
    evidence = tmp_path / "evidence"
    assert (
        main(
            [
                "run",
                str(source),
                "--plan",
                str(config),
                "--output-dir",
                str(evidence),
                "--profile",
                "production",
                "--format",
                output_format,
            ],
            native_tools=native_tools,
        )
        == 1
    )
    output = capsys.readouterr()
    stored = json.loads((evidence / "run.json").read_text(encoding="utf-8"))
    assert stored["failed_stage"] == "audit-remediated"
    assert stored["schema_version"] == 1
    if output_format == "json":
        assert json.loads(output.out)["failed_stage"] == "audit-remediated"
    else:
        assert "Profile: production" in output.out
        assert "Result: failed (exit 1" in output.out
        assert "audit-remediated: gate-failed" in output.out
        assert rules.LINK001.id in (evidence / "REVIEW.md").read_text()
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
            "run",
            str(source),
            "--plan",
            str(config),
            "--output-dir",
            str(tmp_path / "evidence"),
            "--profile",
            "source",
        ])
        == 0
    )
    output = capsys.readouterr().out
    assert "Result: passed (exit 0" in output
    assert "1 warnings" in output
    assert "REVIEW.md" in output


@pytest.mark.parametrize("failure", ["validation failed", "executable unavailable"])
def test_review_does_not_claim_a_failed_validator_was_not_run(failure: str) -> None:
    data = record(status="failed", failed_stage="validate-pdf")
    data = replace(
        data,
        profile=Profile.PRODUCTION,
        stages=(data.stages[0], replace(data.stages[1], outcome=Refused(DocumentRefusal(failure)))),
    )
    text = render_review(data)
    assert "Automated gates: **FAILED**" in text
    assert "Assurance profile: `production`" in text
    assert "veraPDF did not pass" in text
    assert "veraPDF did not run" not in text
    assert "Human review still required" in text


def test_pipeline_failure_shows_source_findings_and_safe_tool_details(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source = Report(kind=ReportKind.ODF, subject="source.odt")
    source.raise_(rules.LINK001)
    data = RunRecord(
        document=DocumentIdentity("doc.odt"),
        fidelity_policy=Pagination.SAME(),
        profile=Profile.SOURCE,
    )
    data = replace(
        data,
        stages=(
            StageResult(Stage.AUDIT_SOURCE, Passed(source)),
            StageResult(
                Stage.REMEDIATE,
                Crashed(
                    ToolFailure(
                        "native tool failed", details="untrusted\x1b[31m\nCommand: completed"
                    )
                ),
            ),
        ),
    )
    config = tmp_path / "plan.toml"
    config.write_text(plan_header(tmp_path / "source.odt") + "", encoding="utf-8")
    monkeypatch.setattr(cli_pipeline.api, "run", lambda *_args, **_kwargs: data)
    assert main(["run", "source.odt", "--plan", str(config), "--output-dir", "evidence"]) == 3
    text = capsys.readouterr().out
    assert "audit-source: passed; 0 errors; 1 warnings" in text
    assert "Result: failed (exit 3" in text
    assert "native tool failed" in text
    assert "\x1b" not in text
    assert "\nCommand: completed" not in text
