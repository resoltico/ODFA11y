# SPDX-License-Identifier: AGPL-3.0-only
"""CLI input refusals terminate promptly and preserve independent audit results."""

import json
import os
import subprocess
import sys
from dataclasses import replace
lazy from pathlib import Path

import pytest
from pypdf.generic import EncodedStreamObject, NameObject, StreamObject

from odfa11y.application.compare import is_pdf
from odfa11y.application.native import NativeTools
from odfa11y.cli import main
from odfa11y.rules import registry as rules
from tests.fixtures.native import refusing
from tests.fixtures.pdf import register, tagged_writer, text_pdf
from tests.fixtures.writer import make_minimal_odt


@pytest.mark.parametrize("operand", ["audit", "source", "candidate"])
def test_fifo_refuses_before_deadline(tmp_path: Path, operand: str) -> None:
    if sys.platform == "win32":
        pytest.skip("POSIX FIFO; Windows file-kind tests run separately")
    fifo = tmp_path / "input"
    os.mkfifo(fifo)
    regular = make_minimal_odt(tmp_path / "regular.odt")
    before = regular.read_bytes()
    executable = tmp_path / "unavailable-tool"
    diff = tmp_path / "diff"
    arguments = (
        ["audit", str(fifo)]
        if operand == "audit"
        else [
            "compare",
            str(fifo if operand == "source" else regular),
            str(fifo if operand == "candidate" else regular),
            "--soffice",
            str(executable),
            "--diff-dir",
            str(diff),
        ]
    )
    result = subprocess.run(
        [sys.executable, "-m", "odfa11y", *arguments],
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
    )
    assert result.returncode == 2
    assert "regular file" in result.stderr
    assert "Traceback" not in result.stderr
    if operand == "audit":
        assert "Result: failed (exit 2" in result.stdout
    else:
        assert not result.stdout
    assert not diff.exists()
    assert regular.read_bytes() == before


@pytest.mark.parametrize("output_format", ["text", "json"])
def test_audit_retains_before_and_after_results_with_strongest_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], output_format: str
) -> None:
    first = make_minimal_odt(tmp_path / "first.odt", features={"with_plain_email": True})
    last = make_minimal_odt(tmp_path / "last.odt", features={"with_image_without_alt": True})
    missing = tmp_path / "missing.odt"
    assert (
        main(["audit", str(first), str(missing), str(last), "--format", output_format, "--strict"])
        == 3
    )
    output = capsys.readouterr()
    assert str(missing) in output.err
    if output_format == "json":
        payload = json.loads(output.out)
        assert payload["exit_status"] == 3
        assert payload["inputs"][1]["failure"]["code"] == "io-failure"
        reports = [report for item in payload["inputs"] for report in item["reports"]]
        assert [report["subject"] for report in reports] == [str(first), str(last)]
        assert reports[0]["summary"]["errors"] == 0
        assert reports[1]["summary"]["errors"] > 0
    else:
        assert "Result: failed (exit 3" in output.out
        assert str(first) in output.out
        assert str(last) in output.out
        assert rules.GRAPHIC001.id in output.out


def test_sniff_regular_alias_and_directory(tmp_path: Path) -> None:
    source = text_pdf(tmp_path / "source", [["Regular"]])
    alias = tmp_path / "alias"
    alias.symlink_to(source)
    assert is_pdf(source)
    assert is_pdf(alias)
    assert main(["audit", str(tmp_path)]) == 2


def test_sniff_checks_opened_file_kind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = text_pdf(tmp_path / "source", [["Regular"]])
    directory_info = tmp_path.stat()
    monkeypatch.setattr(os, "fstat", lambda _: directory_info)
    assert main(["audit", str(source)]) == 2


def test_strict_gate_is_separate_from_json_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "warning.odt", features={"with_plain_email": True})
    assert main(["audit", str(source), "--strict", "--format", "json"]) == 1
    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert payload["inputs"][0]["reports"][0]["summary"]["errors"] == 0
    assert payload["exit_status"] == 1
    assert not output.err


def test_real_unsupported_stream_is_a_structured_audit_and_controlled_compare_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    writer = tagged_writer()
    stream = EncodedStreamObject()
    StreamObject.set_data(stream, b"unsupported content")
    stream[NameObject("/Filter")] = NameObject("/UnestablishedDecode")
    writer.pages[0][NameObject("/Contents")] = register(writer, stream)
    source = tmp_path / "unsupported.pdf"
    writer.write(source)
    before = source.read_bytes()
    assert main(["audit", str(source), "--format", "json"]) == 2
    output = capsys.readouterr()
    report = json.loads(output.out)["inputs"][0]["reports"][0]
    assert [finding["rule_id"] for finding in report["findings"]] == [rules.PDF001.id]
    assert "Unsupported PDF stream decoding" in report["findings"][0]["message"]
    assert not output.err
    assert main(["compare", str(source), str(source)]) == 3
    output = capsys.readouterr()
    assert not output.out
    assert "Unsupported PDF stream decoding" in output.err
    assert "Traceback" not in output.err
    assert source.read_bytes() == before


def test_compare_preflight_rejects_candidate_before_export(
    native_tools: NativeTools, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    calls = []
    native_tools = replace(native_tools, export=refusing(calls))
    assert main(["compare", str(source), str(tmp_path / "missing")], native_tools=native_tools) == 3
    assert not calls


def test_unreadable_input_continues_to_next_audit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    blocked = text_pdf(tmp_path / "blocked.pdf", [["Blocked"]])
    good = make_minimal_odt(tmp_path / "good.odt")
    opener = os.open

    def open_input(path, flags, mode=0o777, *, dir_fd=None) -> int:
        if path == blocked:
            message = "Permission denied"
            raise PermissionError(13, message, str(path))
        return opener(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", open_input)
    assert main(["audit", str(blocked), str(good), "--format", "json"]) == 3
    output = capsys.readouterr()
    assert "Permission denied" in output.err
    assert str(blocked) in output.err
    assert json.loads(output.out)["inputs"][1]["reports"][0]["subject"] == str(good)


@pytest.mark.parametrize("command", ["run", "batch"])
def test_help_explains_profiles_and_timeout(
    capsys: pytest.CaptureFixture[str], command: str
) -> None:
    with pytest.raises(SystemExit) as exited:
        main([command, "--help"])
    assert exited.value.code == 0
    output = " ".join(capsys.readouterr().out.split())
    assert "default: pdf" in output
    assert "Require PDF/UA validation and reject warnings as well as errors." in output
    assert "Seconds per native call (default: 120)" in output
