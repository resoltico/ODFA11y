# SPDX-License-Identifier: MPL-2.0
"""Native durations are validated before side effects and reach real validator work."""

from __future__ import annotations

import math
import os
import sys
import time
from typing import TYPE_CHECKING, cast

import pytest
from pypdf import PdfWriter

from odfa11y.cli import main
from odfa11y.cli.parser import build_parser
from odfa11y.errors import PlanError, ToolFailedError
from odfa11y.external_tools import MAX_TIMEOUT_SECONDS, run_bounded, validate_timeout
from odfa11y.pdf import ExportSettings, check_pdfua, validate_pdfua
from odfa11y.pipeline import NativeOptions, PipelineOptions, audit_document

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        True,
        "1",
        float("nan"),
        float("inf"),
        float("-inf"),
        10**400,
        MAX_TIMEOUT_SECONDS + 0.001,
        math.nextafter(MAX_TIMEOUT_SECONDS, math.inf),
    ],
)
def test_invalid_timeouts_launch_nothing(value: object, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Invalid timeout launched a native process")

    monkeypatch.setattr("odfa11y.external_tools.subprocess.Popen", forbidden)
    invalid_timeout = cast("float", value)
    with pytest.raises(PlanError, match="Timeout"):
        run_bounded([sys.executable], timeout=invalid_timeout)
    for factory in (NativeOptions, PipelineOptions):
        with pytest.raises(PlanError, match="Timeout"):
            factory(timeout=invalid_timeout)
    with pytest.raises(PlanError, match="Timeout"):
        ExportSettings("writer_pdf_Export", timeout=invalid_timeout)
    with pytest.raises(PlanError, match="Timeout"):
        check_pdfua("missing.pdf", subject="missing.pdf", timeout=invalid_timeout)
    with pytest.raises(PlanError, match="Timeout"):
        validate_pdfua("missing.pdf", timeout=invalid_timeout)
    with pytest.raises(PlanError, match="Timeout"):
        list(audit_document("missing.pdf", timeout=invalid_timeout))


@pytest.mark.parametrize(
    "value", [0.001, 0.5, 1, MAX_TIMEOUT_SECONDS, math.nextafter(MAX_TIMEOUT_SECONDS, 0)]
)
def test_valid_fractional_and_portable_boundary_values(value: float) -> None:
    assert validate_timeout(value) == value


@pytest.mark.parametrize("value", ["0", "-1", "nan", "1.5", str(10**400), "4294968"])
def test_cli_timeout_errors_exit_usage_status_before_outputs(tmp_path: Path, value: str) -> None:
    output = tmp_path / "output.pdf"
    with pytest.raises(SystemExit) as exc:
        main(["export", str(tmp_path / "source.odt"), str(output), "--timeout", value])
    assert exc.value.code == 4
    assert not output.exists()


def test_audit_exposes_only_the_relevant_timeout_option() -> None:

    args = build_parser().parse_args(["audit", "file.pdf", "--timeout", "7"])
    assert args.timeout == 7
    assert not hasattr(args, "soffice")


def test_selected_validator_timeout_terminates_actual_invocation(tmp_path: Path) -> None:
    executable = tmp_path / ("slow-validator.cmd" if os.name == "nt" else "slow-validator")
    if os.name == "nt":
        executable.write_text(f'@"{sys.executable}" -c "import time; time.sleep(30)"\n')
    else:
        executable.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(30)\n")
        executable.chmod(0o700)
    pdf = tmp_path / "input.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(pdf)
    started = time.monotonic()
    with pytest.raises(ToolFailedError, match=r"timed out after 0\.1 s"):
        list(audit_document(pdf, verapdf_path=executable, timeout=0.1))
    assert time.monotonic() - started < 10
