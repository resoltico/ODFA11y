# SPDX-License-Identifier: MPL-2.0
"""Physical capture bounds and descriptor-kind checks precede document parsing."""

import hashlib
import importlib
import multiprocessing
import os
import sys
lazy from pathlib import Path

import pytest

from odfa11y import capture
from odfa11y.errors import PackageError
from odfa11y.evidence import check_bundle
from odfa11y.odf import OdfDocument
from odfa11y.plans import Plan
from odfa11y.plans.fidelity import Pagination
from odfa11y.status import Profile
from tests.batch.test_batch import manifest_file
from tests.fixtures.documents import make_flat
from tests.fixtures.plans import plan_header, reviewed_plan
from tests.fixtures.runs import RunSettings, execute, run_batch


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
            assert path.path.read_bytes() == source.read_bytes()
            OdfDocument.open(path.path)
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
    try:
        result = execute(source, reviewed_plan(source), output, RunSettings(profile=Profile.SOURCE))
    except PackageError as error:
        sys.exit(error.exit_status)
    sys.exit(result.exit_status)


def test_fifo_pipeline_refuses_without_waiting_for_a_writer(tmp_path: Path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("POSIX FIFO control")
    source = tmp_path / "input.fodt"
    os.mkfifo(source)
    context = multiprocessing.get_context("spawn")
    output = tmp_path / "evidence"
    child = context.Process(target=_pipeline, args=(str(source), str(output)))
    child.start()
    try:
        child.join(3)
        assert not child.is_alive(), "nonregular source open blocked"
        assert child.exitcode == 2
        assert not output.exists()
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
        assert staged.identity.path.parent == target.resolve()
        assert staged.path.read_bytes() == source.read_bytes()
    assert alias.is_symlink()
    assert asset.read_bytes() == b"sentinel"
    assert not list(target.glob(".odfa11y-source-*"))


def test_descriptor_validation_rejects_replacement_fifo_nonblocking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_flat(tmp_path, "text")
    original = os.open

    def replace(
        path: str | os.PathLike[str], flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        if not hasattr(os, "mkfifo"):
            pytest.skip("POSIX replaced-input FIFO control")
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
    with pytest.raises(PackageError):
        execute(
            source,
            reviewed_plan(source, [], Pagination.SAME()),
            tmp_path / "out",
            RunSettings(profile=Profile.parse("source")),
        )
    assert not (tmp_path / "out").exists()


def test_directory_input_has_valid_execution_failure_evidence(tmp_path: Path) -> None:
    source = tmp_path / "directory.odt"
    source.mkdir()
    output = tmp_path / "evidence"
    with pytest.raises(PackageError):
        execute(
            source,
            reviewed_plan(source, [], Pagination.SAME()),
            output,
            RunSettings(profile=Profile.parse("source")),
        )
    assert not (output).exists()


def test_batch_continues_after_physical_capture_refusal(tmp_path: Path) -> None:
    source = tmp_path / "large.odt"
    with source.open("wb") as stream:
        stream.truncate(270 * 1024 * 1024)
    normal = make_flat(tmp_path, "text")
    (tmp_path / "plan.toml").write_text(
        plan_header(normal) + '[decisions."document.metadata"]\nlanguage="en-GB"'
    )
    manifest = manifest_file(
        tmp_path, [("oversized", source.name, "plan.toml"), ("valid", normal.name, "plan.toml")]
    )
    result = run_batch(
        manifest, tmp_path / "evidence", RunSettings(profile=Profile.parse("source"))
    )
    assert [item.exit_status for item in result.items] == [2, 0]
    assert result.items[0].failed_stage is None
    assert result.items[0].error is not None
    assert not (tmp_path / "evidence" / "oversized").exists()
    assert check_bundle(tmp_path / "evidence" / "valid") == []
    assert not list(tmp_path.glob(".odfa11y-source-*"))


def test_readonly_source_directory_does_not_need_write_access(tmp_path: Path) -> None:
    directory = tmp_path / "readonly"
    directory.mkdir()
    source = make_flat(directory, "text")
    original = source.read_bytes()
    directory.chmod(0o500)
    try:
        if os.access(directory, os.W_OK):
            pytest.skip("The current platform/user does not enforce POSIX directory write modes")
        output = tmp_path / "evidence"
        result = execute(
            source,
            reviewed_plan(source, [], Pagination.SAME()),
            output,
            RunSettings(profile=Profile.parse("source")),
        )
        assert result.failed_stage is None
        assert result.exit_status == 0
        assert check_bundle(output) == []
        assert source.read_bytes() == original
        assert not list(directory.glob(".odfa11y-source-*"))
    finally:
        directory.chmod(0o700)


def test_capture_returns_one_digest_and_plan_reuses_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_flat(tmp_path, "text")
    expected = source.read_bytes()

    def forbidden(_path: Path) -> str:
        pytest.fail("An already captured source was hashed again")

    with capture.capture_source(source) as captured:
        assert captured.digest == hashlib.sha256(expected).hexdigest()
        assert captured.identity.name == source.name
        assert captured.path.parent != source.parent
        monkeypatch.setattr(
            importlib.import_module("odfa11y.plans.model"), "source_digest", forbidden
        )
        assert Plan.for_source(captured).header.source.sha256 == captured.digest
    assert not captured.path.exists()
