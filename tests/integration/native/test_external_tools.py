# SPDX-License-Identifier: MPL-2.0
"""Native integration cases for external tools."""

import json
import multiprocessing
import os
import signal
import sys
from pathlib import Path
lazy from collections.abc import Callable

import pytest

from odfa11y.evidence import check_bundle
from odfa11y.odf import PackageStorage
from tests.batch.test_batch import manifest_file
from tests.fixtures.plans import plan_header
from tests.fixtures.writer import make_minimal_odt
from tests.native.test_external_tools import _native_command


@pytest.mark.parametrize("interrupt", [signal.SIGTERM, signal.SIGINT])
@pytest.mark.parametrize("mode", ["standalone", "batch"])
def test_real_native_termination_cleans_tool_and_preserves_completed_batch(
    tmp_path: Path, external_tool: Callable[..., str], interrupt: int, mode: str
) -> None:
    if sys.platform == "win32":
        pytest.skip("POSIX signals/process groups require separate Windows controls")
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
        (tmp_path / "plan.toml").write_text(
            plan_header(tmp_path / "first.odt")
            + '[decisions."document.metadata"]\ntitle="T"\nlanguage="en"'
        )
        (tmp_path / "second.plan.toml").write_text(
            plan_header(source) + '[decisions."document.metadata"]\ntitle="T"\nlanguage="en"'
        )
        source = manifest_file(
            tmp_path,
            [
                ("first", "first.odt", "plan.toml"),
                ("second", "second-input/source.odt", "second.plan.toml"),
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
