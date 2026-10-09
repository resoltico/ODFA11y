# SPDX-License-Identifier: MPL-2.0
"""Real leaf exchanges reject wrong bytes; parent namespace guarantees remain separate."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from odfa11y.batch import run_batch
from odfa11y.errors import PackageError
from odfa11y.evidence import check_bundle
from odfa11y.fidelity import FidelityPolicy
from odfa11y.pipeline import PipelineOptions, run_pipeline
from odfa11y.pipeline import source as capture

from .documents import make_flat
from .test_batch import manifest_file

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("kind", ["symlink", "regular", "symlink-without-nofollow"])
def test_real_exchange_before_open_is_rejected_without_reading_wrong_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    if kind == "symlink-without-nofollow":
        monkeypatch.setattr(capture.os, "O_NOFOLLOW", 0, raising=False)
    source = make_flat(tmp_path, "text")
    replacement = tmp_path / "replacement.fodt"
    replacement.write_bytes(b"different file identity")
    selected = tmp_path / "selected.fodt"
    source.rename(selected)  # Keep selected inode alive: inode reuse is not this control.
    source.write_bytes(selected.read_bytes())
    original_open = os.open
    original_read = os.read
    reads = []

    def exchange(
        path: str | os.PathLike[str], flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        if path == source:
            source.rename(tmp_path / "before-exchange.fodt")
            if kind.startswith("symlink"):
                source.symlink_to(replacement)
            else:
                os.link(replacement, source)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    def read(descriptor: int, count: int) -> bytes:
        reads.append(descriptor)
        return original_read(descriptor, count)

    monkeypatch.setattr(capture.os, "open", exchange)
    monkeypatch.setattr(capture.os, "read", read)
    with pytest.raises(PackageError, match="identity changed"), capture.capture_source(source):
        pytest.fail("another selected file was captured")
    assert reads == []
    assert replacement.read_bytes() == b"different file identity"
    assert not list(tmp_path.glob(".odfa11y-source-*"))


def test_pipeline_and_batch_retain_identity_failure_evidence_and_continue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_flat(tmp_path, "text")
    other = tmp_path / "other.fodt"
    other.write_bytes(source.read_bytes() + b" ")
    original_open = os.open

    def exchange(
        path: str | os.PathLike[str], flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        if path == source:
            old = tmp_path / "selected.fodt"
            old.unlink(missing_ok=True)
            source.rename(old)
            os.link(other, source)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(capture.os, "open", exchange)
    output = tmp_path / "pipeline"
    record = run_pipeline(source, [], FidelityPolicy(), output, PipelineOptions(profile="inspect"))
    assert record.exit_status == 3
    assert record.failed_stage == "identify-source"
    assert check_bundle(output) == []
    assert not list(output.glob("remediated.*"))
    # Give the next capture a distinct selected inode again.
    source.unlink()
    source.write_bytes(other.read_bytes())
    valid_dir = tmp_path / "valid"
    valid_dir.mkdir()
    valid = make_flat(valid_dir, "text")
    (tmp_path / "plan.toml").write_text('[document]\nlanguage="en-GB"')
    manifest = manifest_file(
        tmp_path,
        [
            ("changed", source.name, "plan.toml"),
            ("valid", valid.relative_to(tmp_path).as_posix(), "plan.toml"),
        ],
    )
    result = run_batch(manifest, tmp_path / "batch", PipelineOptions(profile="inspect"))
    assert [r["exit_status"] for r in result.items] == [3, 0]
    assert result.items[0]["failed_stage"] == "identify-source"
    for name in ["changed", "valid"]:
        assert check_bundle(tmp_path / "batch" / name) == []
    assert not list(tmp_path.glob(".odfa11y-source-*"))


@pytest.mark.parametrize("alias", ["file", "directory"])
def test_deliberate_aliases_use_the_resolved_parent(tmp_path: Path, alias: str) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    source = make_flat(parent, "text")
    link = tmp_path / "alias"
    if alias == "directory":
        link.symlink_to(parent, target_is_directory=True)
        selected = link / source.name
    else:
        link.symlink_to(source)
        selected = link
    with capture.capture_source(selected) as staged:
        assert staged.parent == parent.resolve()
        assert staged.read_bytes() == source.read_bytes()
    assert not staged.exists()
    assert link.is_symlink()


@pytest.mark.parametrize("timing", ["before-open-hardlink", "after-open", "during-copy"])
def test_parent_namespace_changes_are_outside_the_stable_directory_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, timing: str
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    source = make_flat(parent, "text")
    expected = source.read_bytes()
    selected = source.stat()
    moved = tmp_path / "moved"
    original_open, original_read = os.open, os.read
    exchanged = False

    def exchange() -> None:
        nonlocal exchanged
        parent.rename(moved)
        parent.mkdir()
        os.link(moved / source.name, source)
        exchanged = True

    def open_source(
        path: str | os.PathLike[str], flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        if path == source and timing == "before-open-hardlink":
            exchange()
        descriptor = original_open(path, flags, mode, dir_fd=dir_fd)
        if path == source and timing == "after-open":
            try:
                exchange()
            except BaseException:
                os.close(descriptor)
                raise
        return descriptor

    def read(descriptor: int, count: int) -> bytes:
        data = original_read(descriptor, count)
        if data and timing == "during-copy" and not exchanged:
            exchange()
        return data

    monkeypatch.setattr(capture.os, "open", open_source)
    monkeypatch.setattr(capture.os, "read", read)
    try:
        _assert_parent_observation(source, selected, expected, timing)
    except PermissionError:
        # Windows may deny ancestor rename while the input descriptor is open.
        assert os.name == "nt"
        assert parent.is_dir()
        assert not moved.exists()
        assert source.read_bytes() == expected
        assert not list(parent.glob(".odfa11y-source-*"))
    finally:
        for path in moved.glob(".odfa11y-source-*"):
            path.unlink()  # Explicitly clean this unsupported-namespace experiment's owned copy.
    original_parent = moved if moved.exists() else parent
    assert (original_parent / source.name).read_bytes() == expected


def _assert_parent_observation(
    source: Path, selected: os.stat_result, expected: bytes, timing: str
) -> None:
    moved = source.parent.parent / "moved"
    with capture.capture_source(source) as staged:
        assert os.path.samestat(selected, source.stat())  # Leaf identity is unchanged.
        if timing == "during-copy":
            assert not staged.exists()  # Path-based ownership needs stable ancestors.
        else:
            assert staged.read_bytes() == expected
            assert staged.parent.stat().st_ino != moved.stat().st_ino
    retained = list(moved.glob(".odfa11y-source-*"))
    assert len(retained) == (1 if timing == "during-copy" else 0)
    if retained:
        assert retained[0].read_bytes() == expected
