# SPDX-License-Identifier: MPL-2.0
"""Interrupt a real batch process after evidence publication and inspect durable state."""

from __future__ import annotations

import importlib
import json
import multiprocessing
import os
import signal
import sys
from typing import TYPE_CHECKING

import pytest

from odfa11y.evidence import check_bundle
from odfa11y.pipeline import PipelineOptions

from .fixtures import make_minimal_odt
from .test_batch import manifest_file

if TYPE_CHECKING:
    from multiprocessing.synchronize import Event
    from pathlib import Path

    from odfa11y.config import Config


def _blocked_batch(manifest: str, output: str, ready: Event) -> None:
    runner = importlib.import_module("odfa11y.batch.run")
    original = runner.load_config
    count = 0

    def block_second(path: str | Path) -> Config:
        nonlocal count
        count += 1
        if count == 2:
            ready.set()
            multiprocessing.Event().wait(60)
        return original(path)

    patch = pytest.MonkeyPatch()
    patch.setattr(runner, "load_config", block_second)
    result = runner.run_batch(manifest, output, PipelineOptions(profile="inspect"))
    sys.exit(result.exit_status)


@pytest.mark.skipif(sys.platform == "win32", reason="Windows terminate forcibly kills the process")
@pytest.mark.parametrize("interrupt", [signal.SIGTERM, signal.SIGINT])
def test_real_process_interruption_keeps_completed_evidence_and_pending_ids(
    tmp_path: Path, interrupt: int
) -> None:
    make_minimal_odt(tmp_path / "doc.odt")
    (tmp_path / "plan.toml").write_text('[document]\ntitle="T"\nlanguage="en"')
    manifest = manifest_file(
        tmp_path, [(name, "doc.odt", "plan.toml") for name in ("first", "second", "third")]
    )
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    output = tmp_path / "out"
    child = context.Process(target=_blocked_batch, args=(str(manifest), str(output), ready))
    child.start()
    try:
        assert ready.wait(20), "batch did not reach second item"
        running = json.loads((output / "batch.json").read_text())
        assert [item["status"] for item in running["items"]] == ["completed", "running", "pending"]
        assert child.pid is not None
        os.kill(child.pid, interrupt)
        child.join(20)
        assert child.exitcode == 3
        summary = json.loads((output / "batch.json").read_text())
        assert summary["status"] == "interrupted"
        assert summary["exit_status"] == 3
        assert summary["pending_ids"] == ["third"]
        assert [item["status"] for item in summary["items"]] == [
            "completed",
            "interrupted",
            "pending",
        ]
        assert check_bundle(output / "first") == []
        assert not (output / "second").exists()
        assert not (output / "third").exists()
        assert str(tmp_path) not in json.dumps(summary)
    finally:
        if child.is_alive():
            child.kill()
            child.join(20)
        child.close()
