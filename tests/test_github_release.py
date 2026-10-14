# SPDX-License-Identifier: MPL-2.0
"""Failed state queries and identity mismatches must never authorize releases."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from tools import github_release as releases
from tools.github_release import ReleaseExpectation, require_absent, verify_release

if TYPE_CHECKING:
    from pathlib import Path

TARGET = "a" * 40
EXPECTED = ReleaseExpectation(TARGET, {"wheel.whl": b"tested"}, "Exact notes\n")


def install_api(monkeypatch: pytest.MonkeyPatch, refs: object, published: object) -> None:
    def response(_: str, endpoint: str, *, paginate: bool = False) -> object:
        assert paginate
        return refs if endpoint.startswith("git/") else published

    monkeypatch.setattr(releases, "_api", response)


@pytest.mark.parametrize("refs", [[[]], [[{"ref": "refs/tags/v0.7.0-other", "object": {}}]]])
def test_successful_exact_absence_allows_creation(
    monkeypatch: pytest.MonkeyPatch, refs: object
) -> None:
    install_api(monkeypatch, refs, [[]])
    require_absent("owner/repo", "v0.7.0")


@pytest.mark.parametrize("draft", [False, True])
def test_published_or_draft_release_rejects_creation(
    monkeypatch: pytest.MonkeyPatch, *, draft: bool
) -> None:
    install_api(monkeypatch, [[]], [[{"tag_name": "v0.7.0", "draft": draft}]])
    with pytest.raises(ValueError, match="already exists"):
        require_absent("owner/repo", "v0.7.0")


def test_existing_exact_tag_rejects_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    install_api(monkeypatch, [[{"ref": "refs/tags/v0.7.0", "object": {}}]], [[]])
    with pytest.raises(ValueError, match="already exists"):
        require_absent("owner/repo", "v0.7.0")


@pytest.mark.parametrize("invalid", [None, {}, [], [None], [[None]], [[{"wrong": "record"}]]])
def test_malformed_or_incomplete_queries_cannot_be_absence(
    monkeypatch: pytest.MonkeyPatch, invalid: object
) -> None:
    install_api(monkeypatch, invalid, [[]])
    with pytest.raises(ValueError, match=r"GitHub|Release"):
        require_absent("owner/repo", "v0.7.0")


@pytest.mark.parametrize(
    "exception",
    [
        OSError("transport"),
        releases.subprocess.CalledProcessError(1, ["gh", "api"]),
        ValueError("parse"),
    ],
)
def test_authentication_transport_server_and_parse_failure_abort(
    monkeypatch: pytest.MonkeyPatch, exception: Exception
) -> None:
    def fail(*_: object, **__: object) -> object:
        raise exception

    monkeypatch.setattr(releases, "_api", fail)
    with pytest.raises(type(exception)):
        require_absent("owner/repo", "v0.7.0")


@pytest.mark.parametrize(
    "change",
    [{}, {"target_commitish": "b" * 40}, {"body": "Altered"}, {"assets": []}, {"draft": False}],
)
def test_created_draft_binds_target_notes_and_exact_asset_bytes(
    monkeypatch: pytest.MonkeyPatch, change: dict[str, object]
) -> None:
    release = {
        "tag_name": "v0.7.0",
        "draft": True,
        "target_commitish": TARGET,
        "body": EXPECTED.notes,
        "assets": [{"name": "wheel.whl", "id": 1, "size": 6}],
    }
    release.update(change)
    install_api(monkeypatch, [[]], [[release]])
    monkeypatch.setattr(
        releases.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=b"tested"),
    )
    if change:
        with pytest.raises(ValueError, match=r"GitHub|Release"):
            verify_release("owner/repo", "v0.7.0", EXPECTED, draft=True)
    else:
        verify_release("owner/repo", "v0.7.0", EXPECTED, draft=True)


def test_downloaded_bytes_are_compared_independently_of_declared_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = {
        "tag_name": "v0.7.0",
        "draft": True,
        "target_commitish": TARGET,
        "body": EXPECTED.notes,
        "assets": [{"name": "wheel.whl", "id": 1, "size": 6}],
    }
    install_api(monkeypatch, [[]], [[release]])
    monkeypatch.setattr(
        releases.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=b"damage"),
    )
    with pytest.raises(ValueError, match="Downloaded"):
        verify_release("owner/repo", "v0.7.0", EXPECTED, draft=True)


@pytest.mark.parametrize("commit", [TARGET, "b" * 40])
def test_published_tag_must_peel_to_the_tested_commit(
    monkeypatch: pytest.MonkeyPatch, commit: str
) -> None:
    def response(_: str, endpoint: str, *, paginate: bool = False) -> object:
        if endpoint.startswith("releases?"):
            return [
                [
                    {
                        "tag_name": "v0.7.0",
                        "draft": False,
                        "target_commitish": TARGET,
                        "body": EXPECTED.notes,
                        "assets": [{"name": "wheel.whl", "id": 1, "size": 6}],
                    }
                ]
            ]
        if endpoint.startswith("git/matching-"):
            assert paginate
            return [[{"ref": "refs/tags/v0.7.0", "object": {"type": "tag", "sha": "c" * 40}}]]
        return {"object": {"type": "commit", "sha": commit}}

    monkeypatch.setattr(releases, "_api", response)
    monkeypatch.setattr(
        releases.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(stdout=b"tested")
    )
    if commit == TARGET:
        verify_release("owner/repo", "v0.7.0", EXPECTED, draft=False)
    else:
        with pytest.raises(ValueError, match="peel"):
            verify_release("owner/repo", "v0.7.0", EXPECTED, draft=False)


def test_api_process_failure_is_not_discarded_by_the_query_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failed_process(*_args: object, **kwargs: object) -> object:
        assert kwargs["check"] is True
        raise releases.subprocess.CalledProcessError(1, ["gh", "api"])

    monkeypatch.setattr(releases.subprocess, "run", failed_process)
    with pytest.raises(releases.subprocess.CalledProcessError):
        require_absent("owner/repo", "v0.7.0")


def test_manual_release_inspection_selects_only_preserved_distribution_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "dist"
    directory.mkdir()
    for name, content in {
        "candidate.whl": b"wheel",
        "candidate.tar.gz": b"source",
        ".gitignore": b"*",
    }.items():
        (directory / name).write_bytes(content)
    checksums = tmp_path / "SHA256SUMS"
    checksums.write_bytes(b"Preserved checksums")
    notes = tmp_path / "notes.md"
    notes.write_text("Preserved notes")
    captured = []
    monkeypatch.setattr(releases, "verify_release", lambda *args, **_kwargs: captured.append(args))
    monkeypatch.setattr(
        "sys.argv",
        [
            "github_release",
            "draft",
            "owner/repo",
            "v0.7.0",
            "--target",
            TARGET,
            "--directory",
            str(directory),
            "--checksums",
            str(checksums),
            "--notes",
            str(notes),
        ],
    )
    assert releases.main() == 0
    assert len(captured) == 1
    assert captured[0][2].assets == {
        "candidate.whl": b"wheel",
        "candidate.tar.gz": b"source",
        "SHA256SUMS": b"Preserved checksums",
    }


@pytest.mark.parametrize("artifacts", [[], ["one.whl"], ["one.whl", "two.whl", "source.tar.gz"]])
def test_manual_release_inspection_refuses_incomplete_or_ambiguous_assets_before_queries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifacts: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    for name in artifacts:
        (tmp_path / name).write_bytes(b"Invented distribution bytes")
    notes = tmp_path / "notes.md"
    notes.write_text("Notes")
    sums = tmp_path / "SHA256SUMS"
    sums.write_text("Checksums")
    calls = []
    monkeypatch.setattr(releases, "verify_release", lambda *args, **_kwargs: calls.append(args))
    monkeypatch.setattr(
        "sys.argv",
        [
            "github_release",
            "draft",
            "owner/repo",
            "v0.7.0",
            "--target",
            TARGET,
            "--directory",
            str(tmp_path),
            "--checksums",
            str(sums),
            "--notes",
            str(notes),
        ],
    )
    assert releases.main() == 1
    assert calls == []
    assert "inspection failed" in capsys.readouterr().err
