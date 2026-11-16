# SPDX-License-Identifier: MPL-2.0
"""Interrupt a real batch process after evidence publication and inspect durable state."""

import importlib
import json
import multiprocessing
import os
import signal
import sys
lazy from collections.abc import Callable
lazy from multiprocessing.synchronize import Event
lazy from pathlib import Path

import pytest

from odfa11y.cli import main
from odfa11y.evidence import check_bundle
from odfa11y.status import Profile
from tests.batch.test_batch import manifest_file
from tests.fixtures.plans import plan_header
from tests.fixtures.runs import RunSettings, run_batch
from tests.fixtures.writer import make_minimal_odt
lazy from odfa11y.plans import Plan


def _blocked_batch(manifest: str, output: str, ready: Event) -> None:
    runner = importlib.import_module("odfa11y.application.run")
    original = runner.load_plan
    count = 0

    def block_second(path: str | Path) -> Plan:
        nonlocal count
        count += 1
        if count == 2:
            ready.set()
            multiprocessing.Event().wait(60)
        return original(path)

    patch = pytest.MonkeyPatch()
    patch.setattr(runner, "load_plan", block_second)
    sys.exit(main(["batch", manifest, "--output-dir", output, "--profile", "source"]))


@pytest.mark.skipif(sys.platform == "win32", reason="Windows terminate forcibly kills the process")
@pytest.mark.parametrize("interrupt", [signal.SIGTERM, signal.SIGINT])
def test_real_process_interruption_keeps_completed_evidence_and_pending_ids(
    tmp_path: Path, interrupt: int
) -> None:
    make_minimal_odt(tmp_path / "doc.odt")
    (tmp_path / "plan.toml").write_text(
        plan_header(tmp_path / "doc.odt")
        + '[decisions."document.metadata"]\ntitle="T"\nlanguage="en"'
    )
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


def _blocked_publication(manifest: str, output: str, ready: Event, boundary: str) -> None:
    runner = importlib.import_module("odfa11y.application.run")
    publisher = importlib.import_module("odfa11y.evidence.bundle")
    count = 0

    def blocked[**P, R](original: Callable[P, R]) -> Callable[P, R]:
        def block(*args: P.args, **kwargs: P.kwargs) -> R:
            nonlocal count
            result = original(*args, **kwargs)
            count += 1
            if count == 2:
                ready.set()
                multiprocessing.Event().wait(60)
            return result

        return block

    patch = pytest.MonkeyPatch()
    if boundary == "after":
        patch.setattr(runner, "execute", blocked(runner.execute))
    else:
        patch.setattr(publisher, "write_manifest", blocked(publisher.write_manifest))
    run_batch(manifest, output, RunSettings(profile=Profile.SOURCE))


@pytest.mark.parametrize("boundary", ["before", "after"])
def test_forced_kill_at_publication_preserves_completed_bundles(
    tmp_path: Path, boundary: str
) -> None:
    if sys.platform == "win32":
        pytest.skip("SIGKILL publication boundaries are POSIX controls")
    make_minimal_odt(tmp_path / "doc.odt")
    (tmp_path / "plan.toml").write_text(
        plan_header(tmp_path / "doc.odt")
        + '[decisions."document.metadata"]\ntitle="T"\nlanguage="en"'
    )
    manifest = manifest_file(
        tmp_path, [(name, "doc.odt", "plan.toml") for name in ("first", "second", "third")]
    )
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    output = tmp_path / "out"
    child = context.Process(
        target=_blocked_publication, args=(str(manifest), str(output), ready, boundary)
    )
    child.start()
    try:
        assert ready.wait(20)
        assert child.pid is not None
        os.kill(child.pid, signal.SIGKILL)
        child.join(20)
        assert child.exitcode == -signal.SIGKILL
        assert check_bundle(output / "first") == []
        summary = json.loads((output / "batch.json").read_text())
        assert [item["status"] for item in summary["items"]] == ["completed", "running", "pending"]
        assert (output / "second").exists() == (boundary == "after")
        if boundary == "after":
            assert check_bundle(output / "second") == []
        assert not (output / "third").exists()
    finally:
        if child.is_alive():
            child.kill()
            child.join(20)
        child.close()
