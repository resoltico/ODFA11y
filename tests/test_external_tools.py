# SPDX-License-Identifier: MPL-2.0
"""Bounded tool execution: limited output, timeouts, and no process left behind."""

from __future__ import annotations

import json
import multiprocessing
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from odfa11y import external_tools
from odfa11y.batch import run_batch
from odfa11y.cli import main
from odfa11y.evidence import check_bundle
from odfa11y.external_tools import ToolRun, identify, run_bounded
from odfa11y.odf import PackageStorage
from odfa11y.pipeline import PipelineOptions

from .fixtures import make_minimal_odt
from .test_batch import manifest_file

if TYPE_CHECKING:
    from collections.abc import Callable
    from multiprocessing.synchronize import Event

PYTHON = sys.executable


def test_output_is_captured_only_up_to_the_limit_and_the_rest_is_drained() -> None:
    program = "import sys; sys.stdout.write('x' * 1_000_000); sys.stderr.write('e' * 10)"
    run = run_bounded([PYTHON, "-c", program], timeout=30, max_output=1000)
    assert run.returncode == 0
    assert run.stdout == "x" * 1000
    assert run.stderr == "e" * 10
    assert run.truncated


def test_output_that_exactly_fits_is_not_marked_truncated() -> None:
    program = "import sys; sys.stdout.write('hello')"
    fits = run_bounded([PYTHON, "-c", program], timeout=30, max_output=5)
    assert (fits.stdout, fits.truncated) == ("hello", False)
    cut = run_bounded([PYTHON, "-c", program], timeout=30, max_output=4)
    assert (cut.stdout, cut.truncated) == ("hell", True)


def test_the_exit_status_is_reported() -> None:
    assert run_bounded([PYTHON, "-c", "raise SystemExit(7)"], timeout=30).returncode == 7


def test_a_program_that_outlives_its_time_limit_is_killed() -> None:
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        run_bounded([PYTHON, "-c", "import time; time.sleep(60)"], timeout=0.5)
    assert time.monotonic() - started < 30


@pytest.mark.skipif(sys.platform == "win32", reason="checks the POSIX process group")
def test_a_timeout_kills_children_the_program_started(tmp_path: Path) -> None:
    marker = tmp_path / "child.pid"
    program = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(marker)!r}, 'w').write(str(child.pid))\n"
        "time.sleep(60)\n"
    )
    with pytest.raises(subprocess.TimeoutExpired):
        run_bounded([PYTHON, "-c", program], timeout=2)
    pid = int(marker.read_text())
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    pytest.fail("the grandchild process survived the timeout")


def test_identify_reports_unknown_for_a_missing_tool_and_for_silence() -> None:
    assert identify("X", "/definitely/not/here", ("--version",)).version == "unknown"
    silent = identify("X", PYTHON, ("-c", "pass"))
    assert silent.version == "unknown"
    versioned = identify("X", PYTHON, ("-c", "print('X 1.2.3 build')"))
    assert versioned.version == "1.2.3"


@pytest.mark.skipif(sys.platform == "win32", reason="uses POSIX shell and sessions")
def test_a_descendant_holding_the_pipes_cannot_delay_a_finished_program() -> None:
    started = time.monotonic()
    run = run_bounded(["sh", "-c", "sleep 20 & echo hi"], timeout=30)
    assert run.stdout.strip() == "hi"
    assert time.monotonic() - started < 15


@pytest.mark.skipif(sys.platform == "win32", reason="uses POSIX shell and sessions")
def test_the_time_limit_holds_even_when_a_descendant_escapes_the_process_group() -> None:
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        run_bounded(["sh", "-c", "setsid sleep 20 & sleep 30"], timeout=1)
    assert time.monotonic() - started < 15


@pytest.mark.skipif(sys.platform == "win32", reason="uses POSIX signals")
def test_an_interruption_kills_the_tool_instead_of_orphaning_it(tmp_path: Path) -> None:
    marker = tmp_path / "pid"
    program = (
        "import os, signal, sys\n"
        "from odfa11y.external_tools import run_bounded\n"
        "signal.signal(signal.SIGALRM, lambda *_: os.kill(os.getpid(), signal.SIGINT))\n"
        "signal.alarm(1)\n"
        f"run_bounded(['sh', '-c', 'echo $$ > {marker}; exec sleep 25'], timeout=60)\n"
    )
    child = subprocess.run(
        [PYTHON, "-c", program], capture_output=True, text=True, timeout=30, check=False
    )
    assert child.returncode != 0
    pid = int(marker.read_text())
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    pytest.fail("the tool survived the interruption")


def test_windows_identification_reads_the_file_version_instead_of_running_the_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[list[str]] = []

    def fake(command: list[str], *, timeout: float) -> ToolRun:
        seen.append(command)
        assert timeout > 0
        return ToolRun(0, "26.2.6.2\r\n", "", stdout_truncated=False, stderr_truncated=False)

    monkeypatch.setattr(external_tools, "run_bounded", fake)
    monkeypatch.setattr(sys, "platform", "win32")
    identity = external_tools.identify_running_or_by_file(
        "LibreOffice", "C:\\Program Files\\O'Neil\\soffice.exe", ("--version",)
    )
    assert identity.version == "26.2.6.2"
    assert len(seen) == 1
    assert seen[0][0] == "powershell"
    assert "O''Neil" in seen[0][-1]  # a quote in the path cannot end the literal
    assert "--version" not in " ".join(seen[0])


def _native_command(
    paths: tuple[str, str], tool: str, marker: str, ready: Event, mode: str
) -> None:
    source, output = paths
    patch = pytest.MonkeyPatch()

    def observe[**P](
        factory: Callable[P, subprocess.Popen[bytes]],
    ) -> Callable[P, subprocess.Popen[bytes]]:
        def start(*args: P.args, **kwargs: P.kwargs) -> subprocess.Popen[bytes]:
            process = factory(*args, **kwargs)
            command = cast("list[str]", args[0])
            original_wait = process.wait

            def wait(timeout: float | None = None) -> int:
                if "--convert-to" in command and "/second-input/" in command[-1]:
                    Path(marker).write_text(str(process.pid), encoding="utf-8")
                    ready.set()
                return original_wait(timeout)

            patch.setattr(process, "wait", wait)
            return process

        return start

    patch.setattr(external_tools.subprocess, "Popen", observe(external_tools.subprocess.Popen))
    if mode == "standalone":
        sys.exit(main(["export", source, output, "--soffice", tool]))
    result = run_batch(source, output, PipelineOptions(soffice=tool))
    sys.exit(result.exit_status)


@pytest.mark.integration
@pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX signals/process groups require separate Windows controls"
)
@pytest.mark.parametrize("interrupt", [signal.SIGTERM, signal.SIGINT])
@pytest.mark.parametrize("mode", ["standalone", "batch"])
def test_real_native_termination_cleans_tool_and_preserves_completed_batch(
    tmp_path: Path, external_tool: Callable[..., str], interrupt: int, mode: str
) -> None:
    tool = external_tool("soffice", "libreoffice")
    directory = tmp_path / "second-input"
    directory.mkdir()
    source = make_minimal_odt(directory / "source.odt")
    package = PackageStorage(source)
    package.write_member(
        "content.xml",
        package.read("content.xml").replace(
            b"Body paragraph.", b"Body paragraph.</text:p><text:p>" * 5_000 + b"End."
        ),
    )
    package.save(source)
    output = tmp_path / ("out.pdf" if mode == "standalone" else "batch")
    if mode == "batch":
        make_minimal_odt(tmp_path / "first.odt")
        (tmp_path / "plan.toml").write_text('[document]\ntitle="T"\nlanguage="en"')
        source = manifest_file(
            tmp_path,
            [
                ("first", "first.odt", "plan.toml"),
                ("second", "second-input/source.odt", "plan.toml"),
            ],
        )
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    marker = tmp_path / "native.pid"
    child = context.Process(
        target=_native_command, args=((str(source), str(output)), tool, str(marker), ready, mode)
    )
    child.start()
    try:
        assert ready.wait(60), "native tool did not reach its wait boundary"
        pid = int(marker.read_text())
        os.kill(pid, 0)  # The native process actually exists when interruption is sent.
        assert child.pid is not None
        os.kill(child.pid, interrupt)
        child.join(20)
        assert child.exitcode == 3
        with pytest.raises(ProcessLookupError):
            os.killpg(pid, 0)
        if mode == "batch":
            assert check_bundle(output / "first") == []
            summary = json.loads((output / "batch.json").read_text())
            assert [item["status"] for item in summary["items"]] == ["completed", "interrupted"]
        else:
            assert not output.exists()
    finally:
        if child.is_alive():
            child.kill()
            child.join(20)
        child.close()
