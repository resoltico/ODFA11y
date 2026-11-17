# SPDX-License-Identifier: AGPL-3.0-only
"""Human command outcomes describe the actual gate and retain actionable evidence."""

import json
from dataclasses import replace
lazy from pathlib import Path

import pytest

from odfa11y.cli import commands as cli_pipeline
from odfa11y.cli import main
from odfa11y.errors import DocumentRefusal, Remedy, RemedyAction, ToolFailure
from odfa11y.plans.fidelity import Pagination
from odfa11y.progress import Stage
from odfa11y.report import Report
from odfa11y.report.model import ReportKind
from odfa11y.rules import registry as rules
from odfa11y.run.record import RunRecord, StageResult
from odfa11y.run.review import render_review
from odfa11y.status import Crashed, Passed, Profile, Refused
from tests.batch.test_batch import write_batch_file
from tests.fixtures.native import native_fakes
from tests.fixtures.plans import plan_header
from tests.fixtures.records import document_detection, record
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
        document=document_detection(),
        source_name="doc.odt",
        source_sha256="0" * 64,
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


def test_run_refusal_renders_structured_problems_and_embedding_remedy(tmp_path, capsys) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    plan = tmp_path / "plan.toml"
    plan.write_text(plan_header(source))

    def refuse(*args, **kwargs):
        message = "Rendering resource is external"
        raise DocumentRefusal(
            message,
            problems=("External chart\x1b[31m", "Embed the reviewed dependency"),
            remedy=Remedy(RemedyAction.EMBED_RESOURCE, "Chart", "chart.png"),
        )

    native = replace(native_fakes(), export=refuse)
    assert (
        main(
            ["run", str(source), "--plan", str(plan), "--output-dir", str(tmp_path / "out")],
            native_tools=native,
        )
        == 2
    )
    output = capsys.readouterr().out
    assert "External chart\\x1b[31m" in output
    assert "Embed the reviewed dependency" in output
    assert "Next: embed chart.png for Chart in the source application." in output
    assert "\x1b" not in output


def test_batch_preparation_error_renders_every_problem_and_plan_remedy(tmp_path, capsys) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    (tmp_path / "plan.toml").write_text(
        plan_header(source) + "[first_unknown]\nvalue = 1\n[second_unknown]\nvalue = 2\n"
    )
    batch_file = write_batch_file(tmp_path, [("one", "source.odt", "plan.toml")])
    assert (
        main([
            "batch",
            str(batch_file),
            "--output-dir",
            str(tmp_path / "out"),
            "--profile",
            "source",
        ])
        == 4
    )
    output = capsys.readouterr().out
    assert "first_unknown" in output
    assert "second_unknown" in output
    assert "Next: generate a fresh plan for this source and review its answers." in output
    summary = json.loads((tmp_path / "out/batch.json").read_text())
    problems = "\n".join(summary["items"][0]["error"]["problems"])
    assert "first_unknown" in problems
    assert "second_unknown" in problems


@pytest.mark.parametrize(
    ("error_type", "exit_status", "stage_status"),
    [(DocumentRefusal, 2, "refused"), (ToolFailure, 3, "crashed")],
)
def test_completed_batch_runs_render_stage_reasons_and_remedies(
    tmp_path, capsys, error_type, exit_status, stage_status
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    (tmp_path / "plan.toml").write_text(plan_header(source))
    batch_file = write_batch_file(
        tmp_path, [("one", "source.odt", "plan.toml"), ("two", "source.odt", "plan.toml")]
    )

    def fail(*args, **kwargs):
        message = "Rendering resource is external"
        raise error_type(
            message,
            problems=("Embed the reviewed dependency\x1b[31m",),
            remedy=Remedy(RemedyAction.EMBED_RESOURCE, "Chart", "chart.png"),
        )

    target = tmp_path / "out"
    assert (
        main(
            ["batch", str(batch_file), "--output-dir", str(target)],
            native_tools=replace(native_fakes(), export=fail),
        )
        == exit_status
    )
    output = capsys.readouterr().out
    assert output.count("Result:") == 1
    assert "\x1b" not in output
    for identity in ("one", "two"):
        item_text = output.split(f"- {identity}: ", 1)[1]
        if identity == "one":
            item_text = item_text.split("- two: ", 1)[0]
        assert f"export-source: {stage_status}; Rendering resource is external" in item_text
        assert f"export-remediated: {stage_status}; Rendering resource is external" in item_text
        assert item_text.count("Embed the reviewed dependency\\x1b[31m") == 2
        assert item_text.count("Next: embed chart.png for Chart in the source application.") == 2
    summary = json.loads((target / "batch.json").read_text())
    for item in summary["items"]:
        assert set(item) == {"id", "error", "evidence", "failed_stage", "exit_status", "status"}
        assert item["error"] is None
        assert (target / item["id"] / "run.json").is_file()
