# SPDX-License-Identifier: AGPL-3.0-only
"""Command behaviour: output formats, exit statuses and failures without tracebacks."""

import json
lazy from pathlib import Path

import pytest

from odfa11y.cli import main
from odfa11y.rules import registry as rules
from tests.fixtures.pdf import tagged_writer, text_pdf
from tests.fixtures.plans import plan_header
from tests.fixtures.writer import make_minimal_odt

FINDINGS = 2
EXECUTION_FAILURE = 3
CONFIG = (
    '[decisions."document.metadata"]\n'
    'title = "Updated"\n'
    '[decisions."text.linkify_addresses"]\n'
    "enabled = true\n"
)


def config(tmp_path: Path, text: str = CONFIG) -> Path:
    """Write a configuration file.

    Returns
    -------
    Path
        The file path.

    """
    path = tmp_path / "odfa11y.toml"
    path.write_text(plan_header(tmp_path / "a.odt") + text, encoding="utf-8")
    return path


def test_audit_has_one_result_contract_for_single_and_multiple_inputs(
    tmp_path: Path, capsys
) -> None:
    first = make_minimal_odt(tmp_path / "a.odt")
    second = make_minimal_odt(tmp_path / "b.odt")
    assert main(["audit", str(first), "--format", "json"]) == 0
    one = json.loads(capsys.readouterr().out)
    assert one["schema_version"] == 1
    assert len(one["inputs"]) == 1
    report = one["inputs"][0]["reports"][0]
    assert report["kind"] == "odf"
    assert report["summary"]["errors"] == 0
    assert (
        next(item for item in report["facts"] if item["producer"] == "odf-metadata")["title"]
        == "Synthetic accessible document"
    )
    assert main(["audit", str(first), str(second), "--format", "json"]) == 0
    many = json.loads(capsys.readouterr().out)
    assert one.keys() == many.keys()
    assert len(many["inputs"]) == 2


def test_audit_dispatches_on_file_content_and_mixes_kinds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    odt = make_minimal_odt(tmp_path / "a.odt")
    pdf = tmp_path / "t.pdf"
    tagged_writer().write(pdf)
    assert main(["audit", str(odt), str(pdf), "--format", "json"]) == 0
    assert [
        report["kind"]
        for item in json.loads(capsys.readouterr().out)["inputs"]
        for report in item["reports"]
    ] == ["odf", "pdf"]


def test_audit_text_exit_status_and_strict_mode(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    failing = make_minimal_odt(tmp_path / "bad.odt", features={"with_image_without_alt": True})
    assert main(["audit", str(failing)]) == FINDINGS
    output = capsys.readouterr().out
    assert "Result: failed (exit 2)" in output
    assert "graphic.alternative" in output
    warned = make_minimal_odt(tmp_path / "warn.odt", features={"with_plain_email": True})
    assert main(["audit", str(warned)]) == 0
    assert main(["audit", str(warned), "--strict"]) == 1


def test_audit_with_schema_flag_validates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    assert main(["audit", str(source), "--schema", "--format", "json"]) == 0
    assert (
        next(
            item
            for item in json.loads(capsys.readouterr().out)["inputs"][0]["reports"][0]["facts"]
            if item["producer"] == "odf-package"
        )["violation_count"]
        == 0
    )


def test_missing_verapdf_is_a_tool_failure_without_a_fake_finding(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf = tmp_path / "t.pdf"
    tagged_writer().write(pdf)
    arguments = [
        "audit",
        "--validate",
        str(pdf),
        "--verapdf",
        str(tmp_path / "absent"),
        "--format",
        "json",
    ]
    assert main(arguments) == 3
    assert not capsys.readouterr().out
    assert main([*arguments, "--strict"]) == 3


def test_template_prints_a_loadable_commented_configuration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt", features={"with_image_without_alt": True})
    assert main(["plan", str(source)]) == 0
    output = capsys.readouterr().out
    assert '[decisions."graphic.alternative"."content/frame[name=Logo]"]' in output


def test_remediate_reports_each_outcome_and_dry_run_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt", features={"with_plain_email": True})
    destination = tmp_path / "out.odt"
    arguments = ["remediate", str(source), str(destination), "--plan", str(config(tmp_path))]
    assert main([*arguments, "--dry-run"]) == 0
    dry = capsys.readouterr().out
    assert "Preview; nothing written." in dry
    assert not destination.exists()
    assert main(arguments) == 0
    output = capsys.readouterr().out
    assert f"Wrote: {destination}" in output
    assert "applied document.metadata [title]" in output
    assert "Schema: passed; ODF 1.4; 0 before, 0 after, 0 new" in output
    assert destination.is_file()


def test_remediate_json_output_is_structured(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    arguments = [
        "remediate",
        str(source),
        str(tmp_path / "o.odt"),
        "--plan",
        str(config(tmp_path)),
    ]
    assert main([*arguments, "--format", "json", "--dry-run"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["publication"] == "preview"
    assert data["decisions"][0]["kind_id"] == "document.metadata"
    assert data["outcomes"][0]["status"] == "applied"


def test_invalid_target_bindings_return_plan_error_with_exit_4(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    bad = config(
        tmp_path,
        (
            '[decisions."table.headers"."content/table[name=Missing]"]\n'
            "rows = 1\n"
            'fingerprint = "0000000000000000"\n'
        ),
    )
    destination = tmp_path / "out.odt"
    assert main(["remediate", str(source), str(destination), "--plan", str(bad)]) == 4
    assert "must resolve to exactly one source element" in capsys.readouterr().err
    assert not destination.exists()


def test_invalid_configuration_is_reported_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    invalid = config(tmp_path, '[decisions."document.metadata"]\nlanguage = 7\n')
    assert main(["remediate", str(source), str(tmp_path / "o.odt"), "--plan", str(invalid)]) == 4
    error = capsys.readouterr().err
    assert "document.metadata.language" in error
    assert "requires a string" in error
    assert not (tmp_path / "o.odt").exists()


def test_removed_flags_and_commands_are_rejected() -> None:
    for arguments in (
        ["remediate", "a", "b", "--plan", "c", "--title", "x"],
        ["normalize-spacing", "a", "b"],
        ["check-evidence", "a"],
        ["styles", "a"],
        ["export-pdfua", "a", "b"],
    ):
        with pytest.raises(SystemExit) as raised:
            main(arguments)
        assert raised.value.code == 4


def test_styles_prints_usage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    assert main(["audit", str(source), "--format", "json"]) == 0
    rows = next(
        item
        for item in json.loads(capsys.readouterr().out)["inputs"][0]["reports"][0]["facts"]
        if item["producer"] == "text-styles"
    )["paragraph_styles"]
    assert any(row["style"] == "Body" for row in rows)
    assert main(["audit", str(source)]) == 0
    assert "text-styles.paragraph_styles:" in capsys.readouterr().out


def test_compare_pdfs_directly_gates_on_the_policy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lines = [["A line of text", "Another line"]]
    left = text_pdf(tmp_path / "a.pdf", lines, top=180)
    right = text_pdf(tmp_path / "b.pdf", lines, top=140)
    assert main(["compare", str(left), str(left), "--format", "json"]) == 0
    capsys.readouterr()
    diff = tmp_path / "diff"
    assert main(["compare", str(left), str(right), "--diff-dir", str(diff)]) == FINDINGS
    assert rules.FIDELITY005.id in capsys.readouterr().out
    assert any(diff.iterdir())
    relaxed = config(tmp_path, "[fidelity]\nraster_tolerance = 5.0\n")
    assert main(["compare", str(left), str(right), "--plan", str(relaxed)]) == 0


def test_check_evidence_reports_integrity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["verify-evidence", str(tmp_path)]) == FINDINGS
    assert "Cannot read manifest.json" in capsys.readouterr().out


def test_missing_input_file_is_an_error_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["audit", str(tmp_path / "absent.odt")]) == EXECUTION_FAILURE
    assert "error:" in capsys.readouterr().err


def test_pipeline_command_without_libreoffice_fails_with_evidence_and_exit_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "a.odt")
    arguments = [
        "run",
        str(source),
        "--plan",
        str(config(tmp_path)),
        "--soffice",
        str(tmp_path / "none"),
    ]
    assert main([*arguments, "--output-dir", str(tmp_path / "ev")]) == EXECUTION_FAILURE
    output = capsys.readouterr().out
    assert not output
    assert not (tmp_path / "ev").exists()
    assert main([*arguments, "--output-dir", str(tmp_path / "ev"), "--format", "json"]) == 3


def test_verapdf_flag_does_not_swallow_the_next_argument(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", "")
    pdf = tmp_path / "t.pdf"
    tagged_writer().write(pdf)
    assert main(["audit", "--validate", str(pdf), "--format", "json"]) == 3
    assert not capsys.readouterr().out
