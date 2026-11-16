# SPDX-License-Identifier: AGPL-3.0-only
"""Native durations are validated before side effects and reach real validator work."""

import math
import os
import sys
import time
from typing import cast
lazy from pathlib import Path

import pytest
from pypdf import PdfWriter

from odfa11y.application.audit import audit_document
from odfa11y.application.native import NativeTools
from odfa11y.application.tools import Tools
from odfa11y.cli import main
from odfa11y.cli.parser import build_parser
from odfa11y.errors import InvalidOption, ToolFailure
from odfa11y.native.process import run_bounded
from odfa11y.native.tools import ResolvedTools
from odfa11y.tool_timeout import Timeout
from tests.fixtures.native import check_pdfua, export_settings, validate_pdfua, validator_tool


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
        Timeout.MAX_SECONDS + 0.001,
        math.nextafter(Timeout.MAX_SECONDS, math.inf),
    ],
)
def test_invalid_timeouts_launch_nothing(value: object, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Invalid timeout launched a native process")

    monkeypatch.setattr("odfa11y.native.process.subprocess.Popen", forbidden)
    invalid_timeout = cast("float", value)
    with pytest.raises(InvalidOption, match="Timeout"):
        run_bounded([sys.executable], timeout=invalid_timeout)
    with pytest.raises(InvalidOption, match="Timeout"):
        Tools(timeout=invalid_timeout)
    with pytest.raises(InvalidOption, match="Timeout"):
        export_settings("writer_pdf_Export", timeout=invalid_timeout)
    with pytest.raises(InvalidOption, match="Timeout"):
        check_pdfua("missing.pdf", subject="missing.pdf", timeout=invalid_timeout)
    with pytest.raises(InvalidOption, match="Timeout"):
        validate_pdfua("missing.pdf", timeout=invalid_timeout)


@pytest.mark.parametrize(
    "value", [0.001, 0.5, 1, Timeout.MAX_SECONDS, math.nextafter(Timeout.MAX_SECONDS, 0)]
)
def test_valid_fractional_and_portable_boundary_values(value: float) -> None:
    assert Timeout(value) == value


@pytest.mark.parametrize("value", ["0", "-1", "nan", str(10**400), "4294968"])
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
    with pytest.raises(ToolFailure, match=r"timed out after 0\.1 s"):
        list(
            audit_document(
                pdf,
                tools=ResolvedTools(Timeout(0.1), verapdf=validator_tool(executable)),
                native_tools=NativeTools(),
            )
        )
    assert time.monotonic() - started < 10
