# SPDX-License-Identifier: MPL-2.0
"""Real CLI termination unwinds a running tool and its process group."""

from __future__ import annotations

import multiprocessing
import os
import signal
import sys
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from odfa11y.cli import main

from .fixtures import make_minimal_odt


def cli_export(source: str, output: str, executable: str) -> None:
    sys.exit(main(["export", source, output, "--soffice", executable]))


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows forced termination is a separate platform contract"
)
@pytest.mark.parametrize("interrupt", [signal.SIGTERM, signal.SIGINT])
def test_cli_cleans_active_export_tool(tmp_path: Path, interrupt: int) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    marker = tmp_path / "pid"
    executable = tmp_path / "soffice"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import os,sys,time\n"
        "if '--version' in sys.argv:\n"
        " print('LibreOffice 26.8.0.3'); sys.exit(0)\n"
        f"open({str(marker)!r}, 'w').write(str(os.getpid()))\n"
        "time.sleep(60)\n"
    )
    executable.chmod(0o700)
    context = multiprocessing.get_context("spawn")
    child = context.Process(
        target=cli_export, args=(str(source), str(tmp_path / "out.pdf"), str(executable))
    )
    child.start()
    try:
        deadline = time.monotonic() + 20
        while not marker.exists() and time.monotonic() < deadline:
            threading.Event().wait(0.05)
        assert marker.exists()
        pid = int(marker.read_text())
        assert child.pid is not None
        os.kill(child.pid, interrupt)
        child.join(20)
        assert child.exitcode == 3
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
        assert not (tmp_path / "out.pdf").exists()
    finally:
        if child.is_alive():
            child.kill()
            child.join(20)
        child.close()
