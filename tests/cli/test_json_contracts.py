# SPDX-License-Identifier: AGPL-3.0-only
"""Every command publishes its use case contract, independent of input cardinality."""

import json
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

import odfa11y as api
from odfa11y.cli import main
from odfa11y.cli.parser import build_parser
from odfa11y.rules import registry as rules
from tests.batch.test_batch import write_batch_file
from tests.fixtures.documents import Variant, make_flat, make_package
from tests.fixtures.native import native_fakes, refusing
from tests.fixtures.plans import plan_header
from tests.fixtures.schema import assert_record_schema
from tests.fixtures.writer import make_minimal_odt

COMMANDS = (
    "audit",
    "plan",
    "remediate",
    "export",
    "compare",
    "run",
    "batch",
    "verify-evidence",
    "doctor",
)


@pytest.mark.parametrize("command", COMMANDS)
def test_json_is_exactly_the_result_contract(tmp_path: Path, capsys, command: str) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    plan = tmp_path / "plan.toml"
    plan.write_text(plan_header(source))
    original = source.read_bytes()
    native = native_fakes()
    api_dir, cli_dir = tmp_path / "api", tmp_path / "cli"
    api_dir.mkdir()
    cli_dir.mkdir()
    match command:
        case "audit":
            result = api.audit(source, native_tools=native)
            arguments = [command, str(source)]
        case "plan":
            result = api.plan(source)
            arguments = [command, str(source)]
        case "remediate":
            result = api.remediate(source, api_dir / "reviewed.odt", plan)
            arguments = [command, str(source), str(cli_dir / "reviewed.odt"), "--plan", str(plan)]
        case "export":
            result = api.export(source, api_dir / "publication.pdf", native_tools=native)
            arguments = [command, str(source), str(cli_dir / "publication.pdf")]
        case "compare":
            result = api.compare(source, source, native_tools=native)
            arguments = [command, str(source), str(source)]
        case "run":
            result = api.run(source, plan, api_dir / "evidence", profile=api.Profile.SOURCE)
            arguments = [
                command,
                str(source),
                "--plan",
                str(plan),
                "--output-dir",
                str(cli_dir / "evidence"),
                "--profile",
                "source",
            ]
        case "batch":
            batch_file = write_batch_file(tmp_path, [("one", "source.odt", "plan.toml")])
            result = api.batch(batch_file, api_dir / "evidence", profile=api.Profile.SOURCE)
            arguments = [
                command,
                str(batch_file),
                "--output-dir",
                str(cli_dir / "evidence"),
                "--profile",
                "source",
            ]
        case "verify-evidence":
            directory = api_dir / "evidence"
            api.run(source, plan, directory, profile=api.Profile.SOURCE)
            result = api.verify_evidence(directory)
            arguments = [command, str(directory)]
        case "doctor":
            result = api.doctor(native_tools=native)
            arguments = [command]
    expected = assert_record_schema(result)
    assert main([*arguments, "--format", "json"], native_tools=native) == result.exit_status
    captured = capsys.readouterr()
    assert json.loads(captured.out) == expected
    assert not captured.err
    assert source.read_bytes() == original


@pytest.mark.parametrize("count", [1, 2])
def test_audit_cardinality_does_not_change_the_json_envelope(
    tmp_path: Path, capsys, count: int
) -> None:
    paths = [make_minimal_odt(tmp_path / f"source-{index}.odt") for index in range(count)]
    expected = assert_record_schema(api.audit(paths))
    assert main(["audit", *(str(path) for path in paths), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out) == expected


@pytest.mark.parametrize("command", ["pipeline", "verify"])
def test_retired_commands_are_refused_without_work(tmp_path: Path, capsys, command: str) -> None:
    with pytest.raises(SystemExit) as stopped:
        main([command, str(tmp_path / "missing")])
    assert stopped.value.code == 4
    assert not list(tmp_path.iterdir())
    assert not capsys.readouterr().out


def test_every_positional_has_help_and_shared_options_have_one_description() -> None:
    root = build_parser()
    sub = next(action for action in root._actions if action.dest == "command")
    assert isinstance(sub.choices, dict)
    descriptions = {}
    for parser in sub.choices.values():
        for action in parser._actions:
            assert action.help
            for option in action.option_strings:
                descriptions.setdefault(option, set()).add(action.help)
    assert all(len(variants) == 1 for variants in descriptions.values())


@pytest.mark.parametrize("command", COMMANDS)
def test_unknown_output_format_is_a_usage_error(command: str, tmp_path: Path) -> None:
    required = {
        "audit": ["source.odt"],
        "plan": ["source.odt"],
        "remediate": ["source.odt", "out.odt", "--plan", "plan.toml"],
        "export": ["source.odt", "out.pdf"],
        "compare": ["a.pdf", "b.pdf"],
        "run": ["source.odt", "--plan", "plan.toml", "--output-dir", str(tmp_path / "out")],
        "batch": ["batch.toml", "--output-dir", str(tmp_path / "out")],
        "verify-evidence": ["evidence"],
        "doctor": [],
    }
    with pytest.raises(SystemExit) as stopped:
        main([command, *required[command], "--format", "yaml"])
    assert stopped.value.code == 4
    assert not list(tmp_path.iterdir())


def test_text_has_one_findings_header_and_ends_with_the_core_verdict(
    tmp_path: Path, capsys
) -> None:
    source = make_minimal_odt(tmp_path / "warning.odt", features={"with_plain_email": True})
    assert main(["audit", str(source), "--strict"]) == 1
    text = capsys.readouterr().out
    assert text.count("Findings:") == 1
    assert text.count("Result:") == 1
    assert (
        text.index("Findings:")
        < text.index("Open decisions:")
        < text.index("Facts:")
        < text.index("Result:")
    )
    assert "Result: failed (exit 1)" in text


def test_sarif_preflight_happens_before_any_required_native_tool(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    root = tmp_path / "confined"
    root.mkdir()
    calls = []
    native = replace(
        native_fakes(), validator=refusing(calls), locate=refusing(calls), export=refusing(calls)
    )
    with pytest.raises(api.InvalidOption):
        api.audit(source, validate_pdf=True, sarif=api.SarifOptions(root), native_tools=native)
    with pytest.raises(api.InvalidOption):
        api.compare(source, source, sarif=api.SarifOptions(root), native_tools=native)
    assert not calls


def test_sarif_failure_keeps_the_specific_reason_without_private_diagnostics(
    tmp_path: Path, capsys
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")

    def fail(*args, **kwargs):
        message = r"Conversion refused for C:\Users\private-person\document.odt and https://user:secret@example.test/"
        raise api.ToolFailure(message, details="PRIVATE raw diagnostic payload")

    native = replace(native_fakes(), export=fail)
    assert (
        main(
            [
                "compare",
                str(source),
                str(source),
                "--format",
                "sarif",
                "--source-root",
                str(tmp_path),
            ],
            native_tools=native,
        )
        == 3
    )
    output = capsys.readouterr()
    assert not output.out
    assert "Conversion refused" in output.err
    assert "private-person" not in output.err
    assert "user:secret" not in output.err
    assert "PRIVATE" not in output.err


def test_root_exposes_machine_rendering_without_retired_presentation_helpers() -> None:
    for name in (
        "terminal_text",
        "render_reports",
        "FORMATS",
        "plan_blockers",
        "failure_status",
        "validate_timeout",
        "DEFAULT_TIMEOUT_SECONDS",
        "run_batch",
        "AuditRun",
    ):
        assert not hasattr(api, name), name
    assert callable(api.render_json)
    assert callable(api.render_sarif)


def test_batch_invalid_profile_is_refused_before_creating_output(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    (tmp_path / "plan.toml").write_text(plan_header(source))
    batch_file = write_batch_file(tmp_path, [("one", source.name, "plan.toml")])
    with pytest.raises(api.InvalidOption):
        api.batch(batch_file, tmp_path / "output", profile=cast(api.Profile, "source"))
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("author", [make_flat, make_package], ids=["flat", "package"])
def test_unknown_odf_media_type_retains_public_package_diagnostics(
    tmp_path, capsys, author
) -> None:
    source = author(
        tmp_path, "text", Variant(media_type="application/vnd.oasis.opendocument.unknown")
    )
    original = source.read_bytes()
    result = api.audit(source)
    assert len(result.reports) == 1
    assert not result.failures
    assert not result.inputs[0].plannable
    assert rules.ODF006.id in {finding.rule_id for finding in result.reports[0].findings}
    assert result.reports[0].facts
    assert result.exit_status == 2
    expected = assert_record_schema(result)
    assert main(["audit", str(source), "--format", "json"]) == 2
    assert json.loads(capsys.readouterr().out) == expected
    assert source.read_bytes() == original


@pytest.mark.parametrize("content", [b"Unrelated text", b"<root/>"])
def test_unrelated_input_remains_a_public_input_failure(tmp_path, capsys, content) -> None:
    source = tmp_path / "input.bin"
    source.write_bytes(content)
    result = api.audit(source)
    assert not result.reports
    assert isinstance(result.inputs[0].error, api.DocumentRefusal)
    assert main(["audit", str(source), "--format", "json"]) == 2
    assert json.loads(capsys.readouterr().out) == assert_record_schema(result)
