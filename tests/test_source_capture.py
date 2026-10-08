# SPDX-License-Identifier: MPL-2.0
"""Physical capture bounds and descriptor-kind checks precede document parsing."""

from __future__ import annotations

import json
import multiprocessing
import os
import sys
from typing import TYPE_CHECKING

import pytest

from odfa11y.batch import run_batch
from odfa11y.errors import PackageError
from odfa11y.evidence import check_bundle
from odfa11y.fidelity import FidelityPolicy
from odfa11y.odf import OdfDocument
from odfa11y.pipeline import PipelineOptions, run_pipeline
from odfa11y.pipeline import source as capture

from .documents import make_flat
from .test_batch import manifest_file

if TYPE_CHECKING:
    from pathlib import Path


def test_oversized_sparse_input_is_refused_without_copying(tmp_path: Path) -> None:
    source = tmp_path / "large.odt"
    with source.open("wb") as stream:
        stream.truncate(270 * 1024 * 1024)
    with pytest.raises(PackageError, match="physical"), capture.capture_source(source):
        pytest.fail("oversized input was captured")
    assert not list(tmp_path.glob(".odfa11y-source-*"))


@pytest.mark.parametrize("difference", [-1, 0, 1])
def test_valid_document_at_physical_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, difference: int
) -> None:
    source = make_flat(tmp_path, "text")
    monkeypatch.setattr(
        capture, "MAX_SOURCE_BYTES", source.stat().st_size + difference, raising=False
    )
    if difference < 0:
        with pytest.raises(PackageError, match="physical"), capture.capture_source(source):
            pytest.fail("over-limit input was accepted")
    else:
        with capture.capture_source(source) as path:
            assert path.read_bytes() == source.read_bytes()
            OdfDocument.open(path)
    assert not list(tmp_path.glob(".odfa11y-source-*"))


def test_growth_after_descriptor_size_check_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_flat(tmp_path, "text")
    original = os.fstat
    monkeypatch.setattr(capture, "MAX_SOURCE_BYTES", source.stat().st_size, raising=False)

    def grow(descriptor: int) -> os.stat_result:
        result = original(descriptor)
        with source.open("ab") as stream:
            stream.write(b" " * 100)
        return result

    monkeypatch.setattr(capture.os, "fstat", grow, raising=False)
    with pytest.raises(PackageError, match="physical"), capture.capture_source(source):
        pytest.fail("growing input bypassed the cap")
    assert not list(tmp_path.glob(".odfa11y-source-*"))


def _pipeline(source: str, output: str) -> None:
    result = run_pipeline(source, [], FidelityPolicy(), output, PipelineOptions(profile="inspect"))
    sys.exit(result.exit_status)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO control")
def test_fifo_pipeline_refuses_without_waiting_for_a_writer(tmp_path: Path) -> None:
    source = tmp_path / "input.fodt"
    os.mkfifo(source)
    context = multiprocessing.get_context("spawn")
    output = tmp_path / "evidence"
    child = context.Process(target=_pipeline, args=(str(source), str(output)))
    child.start()
    try:
        child.join(3)
        assert not child.is_alive(), "nonregular source open blocked"
        assert child.exitcode == 3
        record = json.loads((output / "run.json").read_text())
        assert record["failed_stage"] == "identify-source"
        assert check_bundle(output) == []
        assert not list(tmp_path.glob(".odfa11y-source-*"))
    finally:
        if child.is_alive():
            child.kill()
            child.join(5)
        child.close()


@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
def test_partial_capture_is_removed_on_read_failure_or_interruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: type[BaseException]
) -> None:
    source = make_flat(tmp_path, "text")
    expected = source.read_bytes()
    original = os.read
    calls = 0

    def read(descriptor: int, count: int) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise failure
        return original(descriptor, count)

    monkeypatch.setattr(capture.os, "read", read)
    with pytest.raises(failure), capture.capture_source(source):
        pytest.fail("read failure was hidden")
    assert source.read_bytes() == expected
    assert not list(tmp_path.glob(".odfa11y-source-*"))


def test_regular_symlink_uses_resolved_directory_and_leaves_assets_unchanged(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    source = make_flat(target, "text")
    alias = tmp_path / "alias.fodt"
    alias.symlink_to(source)
    asset = target / "asset"
    asset.write_bytes(b"sentinel")
    with capture.capture_source(alias) as staged:
        assert staged.parent == target.resolve()
        assert staged.read_bytes() == source.read_bytes()
    assert alias.is_symlink()
    assert asset.read_bytes() == b"sentinel"
    assert not list(target.glob(".odfa11y-source-*"))


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX replaced-input FIFO control")
def test_descriptor_validation_rejects_replacement_fifo_nonblocking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_flat(tmp_path, "text")
    original = os.open

    def replace(
        path: str | os.PathLike[str], flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        source.unlink()
        os.mkfifo(source)
        return original(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(capture.os, "open", replace)
    with pytest.raises(PackageError, match="regular file"), capture.capture_source(source):
        pytest.fail("replacement FIFO was consumed")
    assert not list(tmp_path.glob(".odfa11y-source-*"))


def test_zero_length_input_retains_invalid_document_outcome(tmp_path: Path) -> None:
    source = tmp_path / "empty.odt"
    source.write_bytes(b"")
    result = run_pipeline(
        source, [], FidelityPolicy(), tmp_path / "out", PipelineOptions(profile="inspect")
    )
    assert result.failed_stage == "audit-source"
    assert result.exit_status == 2
    assert check_bundle(tmp_path / "out") == []


def test_directory_input_has_valid_execution_failure_evidence(tmp_path: Path) -> None:
    source = tmp_path / "directory.odt"
    source.mkdir()
    output = tmp_path / "evidence"
    result = run_pipeline(source, [], FidelityPolicy(), output, PipelineOptions(profile="inspect"))
    assert result.failed_stage == "identify-source"
    assert result.exit_status == 3
    assert check_bundle(output) == []


def test_batch_continues_after_physical_capture_refusal(tmp_path: Path) -> None:
    source = tmp_path / "large.odt"
    with source.open("wb") as stream:
        stream.truncate(270 * 1024 * 1024)
    normal = make_flat(tmp_path, "text")
    (tmp_path / "plan.toml").write_text('[document]\nlanguage="en-GB"')
    manifest = manifest_file(
        tmp_path, [("oversized", source.name, "plan.toml"), ("valid", normal.name, "plan.toml")]
    )
    result = run_batch(manifest, tmp_path / "evidence", PipelineOptions(profile="inspect"))
    assert [item["exit_status"] for item in result.items] == [3, 0]
    assert result.items[0]["failed_stage"] == "identify-source"
    for name in ["oversized", "valid"]:
        assert check_bundle(tmp_path / "evidence" / name) == []
    assert not list(tmp_path.glob(".odfa11y-source-*"))


def test_unwritable_source_directory_publishes_failure_elsewhere(tmp_path: Path) -> None:
    directory = tmp_path / "readonly"
    directory.mkdir()
    source = make_flat(directory, "text")
    original = source.read_bytes()
    directory.chmod(0o500)
    try:
        if os.access(directory, os.W_OK):
            pytest.skip("The current platform/user does not enforce POSIX directory write modes")
        output = tmp_path / "evidence"
        result = run_pipeline(
            source, [], FidelityPolicy(), output, PipelineOptions(profile="inspect")
        )
        assert result.failed_stage == "identify-source"
        assert result.exit_status == 3
        assert check_bundle(output) == []
        assert source.read_bytes() == original
        assert not list(directory.glob(".odfa11y-source-*"))
    finally:
        directory.chmod(0o700)
