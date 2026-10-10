# SPDX-License-Identifier: MPL-2.0
"""CLI input refusals terminate promptly and preserve independent audit results."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from pypdf.generic import EncodedStreamObject, NameObject, StreamObject

from odfa11y.cli import commands, main
from odfa11y.cli.audit import is_pdf

from .fixtures import make_minimal_odt
from .pdf_fixtures import register, tagged_writer, text_pdf

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX FIFO; Windows file-kind tests run separately"
)
@pytest.mark.parametrize("operand", ["audit", "source", "candidate"])
def test_fifo_refuses_before_deadline(tmp_path: Path, operand: str) -> None:
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
    assert result.returncode == 3
    assert "regular file" in result.stderr
    assert "Traceback" not in result.stderr
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
    assert "Command gate (--strict): FAIL (exit 3)" in output.err
    if output_format == "json":
        reports = json.loads(output.out)
        assert [report["subject"] for report in reports] == [str(first), str(last)]
        assert reports[0]["passed"]
        assert not reports[1]["passed"]
    else:
        assert str(first) in output.out
        assert str(last) in output.out
        assert "TXT010" in output.out


def test_sniff_regular_alias_and_directory(tmp_path: Path) -> None:
    source = text_pdf(tmp_path / "source", [["Regular"]])
    alias = tmp_path / "alias"
    alias.symlink_to(source)
    assert is_pdf(source)
    assert is_pdf(alias)
    assert main(["audit", str(tmp_path)]) == 3


def test_sniff_checks_opened_file_kind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = text_pdf(tmp_path / "source", [["Regular"]])
    directory_info = tmp_path.stat()
    monkeypatch.setattr(os, "fstat", lambda _: directory_info)
    assert main(["audit", str(source)]) == 3


def test_strict_gate_is_separate_from_json_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_minimal_odt(tmp_path / "warning.odt", features={"with_plain_email": True})
    assert main(["audit", str(source), "--strict", "--format", "json"]) == 1
    output = capsys.readouterr()
    assert json.loads(output.out)["passed"]
    assert "Command gate (--strict): FAIL (exit 1)" in output.err


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
    report = json.loads(output.out)
    assert [finding["rule_id"] for finding in report["findings"]] == ["PDF000"]
    assert "Unsupported PDF stream decoding" in report["findings"][0]["message"]
    assert not output.err
    assert main(["compare", str(source), str(source)]) == 3
    output = capsys.readouterr()
    assert not output.out
    assert "Unsupported PDF stream decoding" in output.err
    assert "Traceback" not in output.err
    assert source.read_bytes() == before


def test_compare_preflight_rejects_candidate_before_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    calls = []
    monkeypatch.setattr(commands, "export_pdfua", lambda *args: calls.append(args))
    assert main(["compare", str(source), str(tmp_path / "missing")]) == 3
    assert not calls


def test_unreadable_input_continues_to_next_audit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    blocked = text_pdf(tmp_path / "blocked.pdf", [["Blocked"]])
    good = make_minimal_odt(tmp_path / "good.odt")
    opener = os.open

    def open_input(path: Path, flags: int) -> int:
        if path == blocked:
            message = "Permission denied"
            raise PermissionError(message)
        return opener(path, flags)

    monkeypatch.setattr(os, "open", open_input)
    assert main(["audit", str(blocked), str(good), "--format", "json"]) == 3
    output = capsys.readouterr()
    assert "Permission denied" in output.err
    assert str(blocked) in output.err
    assert json.loads(output.out)["subject"] == str(good)


@pytest.mark.parametrize("command", ["pipeline", "batch"])
def test_help_explains_profiles_and_timeout(
    capsys: pytest.CaptureFixture[str], command: str
) -> None:
    with pytest.raises(SystemExit) as exited:
        main([command, "--help"])
    assert exited.value.code == 0
    output = " ".join(capsys.readouterr().out.split())
    assert "default: verify" in output
    assert "production also requires veraPDF and gates warnings" in output
    assert "seconds (default: 120)" in output
