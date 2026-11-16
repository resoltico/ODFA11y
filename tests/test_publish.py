# SPDX-License-Identifier: MPL-2.0
"""Publication preserves occupied destinations and publishes complete durable bytes."""

import os
from pathlib import Path

import pytest

from odfa11y.errors import IoFailure, OutputOccupied
from odfa11y.publish import publish_directory, publish_file


def test_existing_file_needs_explicit_replacement(tmp_path: Path) -> None:
    target = tmp_path / "output"
    target.write_bytes(b"original")
    with pytest.raises(OutputOccupied):
        publish_file(target, lambda stream: stream.write(b"new"))
    assert target.read_bytes() == b"original"
    assert publish_file(target, lambda stream: stream.write(b"new"), replace=True) == target
    assert target.read_bytes() == b"new"
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("replace", [False, True])
@pytest.mark.parametrize("dangling", [False, True])
def test_symlink_destinations_are_always_refused(
    tmp_path: Path, *, replace: bool, dangling: bool
) -> None:
    victim = tmp_path / "victim"
    if not dangling:
        victim.write_bytes(b"protected")
    target = tmp_path / "link"
    try:
        target.symlink_to(victim)
    except OSError:
        pytest.skip("Symlinks unavailable on this host")
    with pytest.raises(OutputOccupied):
        publish_file(target, lambda stream: stream.write(b"new"), replace=replace)
    assert target.is_symlink()
    assert victim.read_bytes() == b"protected" if not dangling else not victim.exists()


def test_destination_created_during_writing_is_not_overwritten(tmp_path: Path) -> None:
    target = tmp_path / "output"

    def write(stream) -> None:
        stream.write(b"new")
        target.write_bytes(b"concurrent")

    with pytest.raises(OutputOccupied):
        publish_file(target, write)
    assert target.read_bytes() == b"concurrent"
    assert list(tmp_path.iterdir()) == [target]


def test_kernel_no_clobber_applies_after_the_final_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "output"
    link = os.link

    def concurrent(source, destination) -> None:
        target.write_bytes(b"concurrent")
        link(source, destination)

    monkeypatch.setattr(os, "link", concurrent)
    with pytest.raises(OutputOccupied, match="appeared"):
        publish_file(target, lambda stream: stream.write(b"new"))
    assert target.read_bytes() == b"concurrent"
    assert list(tmp_path.iterdir()) == [target]


def test_failed_writer_keeps_the_previous_file_and_cleans_staging(tmp_path: Path) -> None:
    target = tmp_path / "output"
    target.write_bytes(b"original")

    def write(stream) -> None:
        stream.write(b"incomplete")
        message = "producer bug"
        raise ValueError(message)

    with pytest.raises(ValueError, match="producer bug"):
        publish_file(target, write, replace=True)
    assert target.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [target]


def test_failed_file_sync_never_commits_the_new_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "output"
    target.write_bytes(b"original")

    def refuse(_descriptor: int) -> None:
        message = "sync unavailable"
        raise OSError(message)

    monkeypatch.setattr(os, "fsync", refuse)
    with pytest.raises(IoFailure, match="sync unavailable"):
        publish_file(target, lambda stream: stream.write(b"new"), replace=True)
    assert target.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [target]


def test_a_destination_changed_to_a_symlink_during_writing_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "output"
    victim = tmp_path / "victim"
    target.write_bytes(b"original")
    victim.write_bytes(b"protected")
    try:
        (tmp_path / "probe").symlink_to(victim)
    except OSError:
        pytest.skip("Symlinks unavailable on this host")
    (tmp_path / "probe").unlink()

    def write(stream) -> None:
        stream.write(b"new")
        target.unlink()
        target.symlink_to(victim)

    with pytest.raises(OutputOccupied):
        publish_file(target, write, replace=True)
    assert target.is_symlink()
    assert victim.read_bytes() == b"protected"


@pytest.mark.parametrize("occupied", [False, True])
def test_directory_publication_only_replaces_an_empty_directory(
    tmp_path: Path, *, occupied: bool
) -> None:
    staged = tmp_path / "staged"
    staged.mkdir()
    publish_file(staged / "data", lambda stream: stream.write(b"complete"))
    target = tmp_path / "output"
    target.mkdir()
    if occupied:
        (target / "existing").write_bytes(b"keep")
        with pytest.raises(OutputOccupied):
            publish_directory(staged, target)
        assert (target / "existing").read_bytes() == b"keep"
        assert (staged / "data").read_bytes() == b"complete"
    else:
        publish_directory(staged, target)
        assert (target / "data").read_bytes() == b"complete"
        assert not staged.exists()
