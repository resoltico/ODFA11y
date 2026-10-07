# SPDX-License-Identifier: MPL-2.0
"""Batch continuation, strict inputs, confined publication and privacy."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from odfa11y.batch import load_manifest, run_batch
from odfa11y.batch.manifest import preflight
from odfa11y.batch.record import BatchRecord
from odfa11y.errors import ConfigError, OutputError
from odfa11y.evidence import check_bundle
from odfa11y.pipeline import PipelineOptions

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from collections.abc import Sequence

    from odfa11y.adapter import Operation
    from odfa11y.fidelity import FidelityPolicy
    from odfa11y.pipeline import RunRecord


def manifest_file(tmp_path: Path, entries: list[tuple[str, str, str]]) -> Path:
    """Create independently specified batch inputs.

    Returns
    -------
    Path
        The TOML manifest.

    """
    path = tmp_path / "batch.toml"
    path.write_text(
        "\n".join(
            f'[[documents]]\nid = "{identity}"\nsource = "{source}"\nplan = "{plan}"\n'
            for identity, source, plan in entries
        )
    )
    return path


def test_batch_continues_after_bad_plan_missing_source_and_gate_failure(tmp_path: Path) -> None:
    make_minimal_odt(tmp_path / "doc.odt")
    (tmp_path / "plan.toml").write_text('[document]\ntitle = "Invented title"\nlanguage = "en"\n')
    (tmp_path / "bad.toml").write_text("[misspelled]\nx = 1")
    (tmp_path / "broken.odt").write_bytes(b"invalid document")
    manifest = manifest_file(
        tmp_path,
        [
            ("badplan", "doc.odt", "bad.toml"),
            ("missing", "missing.odt", "plan.toml"),
            ("broken", "broken.odt", "plan.toml"),
            ("valid", "doc.odt", "plan.toml"),
        ],
    )
    record = run_batch(manifest, tmp_path / "out", PipelineOptions(profile="inspect"))
    assert record.status == "failed"
    assert record.exit_status == 3
    assert [item["exit_status"] for item in record.items] == [3, 3, 2, 0]
    assert record.items[-1]["status"] == "completed"
    summary = (tmp_path / "out" / "batch.json").read_text()
    assert str(tmp_path) not in summary
    assert "doc.odt" not in summary
    assert json.loads(summary)["pending_ids"] == []
    assert all(check_bundle(tmp_path / "out" / item["id"]) == [] for item in record.items)


@pytest.mark.parametrize(
    "identity", ["../escape", "CON", "nul", "A.B", "space name", "x" * 65, "é", "batch.json"]
)
def test_unsafe_ids_rejected_without_output(tmp_path: Path, identity: str) -> None:
    manifest = manifest_file(tmp_path, [(identity, "doc.odt", "plan.toml")])
    with pytest.raises(ConfigError):
        run_batch(manifest, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_case_collision_is_global_preflight(tmp_path: Path) -> None:
    manifest = manifest_file(tmp_path, [("Doc", "a", "p"), ("doc", "b", "q")])
    with pytest.raises(ConfigError, match="unique"):
        run_batch(manifest, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "contents",
    [
        "",
        "documents = []",
        "documents = 4",
        '[[documents]]\nid="a"\nsource="a"\nplan="p"\nextra=true',
        '[[documents]]\nid="a"\nsource="/absolute"\nplan="p"',
        '[[documents]]\nid="a"\nsource=1\nplan="p"',
    ],
)
def test_strict_manifest_rejects_wrong_shapes(tmp_path: Path, contents: str) -> None:
    manifest = tmp_path / "batch.toml"
    manifest.write_text(contents)
    with pytest.raises(ConfigError):
        load_manifest(manifest)


def test_occupied_output_and_hardlink_are_preserved(tmp_path: Path) -> None:
    manifest = manifest_file(tmp_path, [("doc", "a", "p")])
    output = tmp_path / "out"
    os.link(manifest, output)
    before = manifest.read_bytes()
    with pytest.raises(OutputError):
        run_batch(manifest, output)
    assert output.read_bytes() == manifest.read_bytes() == before


def test_symlink_output_and_ancestor_are_rejected(tmp_path: Path) -> None:
    manifest = manifest_file(tmp_path, [("doc", "a", "p")])
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    for output in (alias, alias / "out"):
        with pytest.raises(OutputError, match="symbolic"):
            run_batch(manifest, output)
    assert list(real.iterdir()) == []


def test_input_under_future_output_is_rejected_before_creation(tmp_path: Path) -> None:
    manifest = manifest_file(tmp_path, [("doc", "out/document.odt", "p")])
    with pytest.raises(OutputError, match="contain"):
        preflight(manifest, tmp_path / "out", load_manifest(manifest))
    assert not (tmp_path / "out").exists()


def test_repeated_sources_and_hardlinked_plans_are_read_only(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    plan = tmp_path / "plan.toml"
    plan.write_text('[document]\ntitle = "T"\nlanguage = "en"')
    os.link(plan, tmp_path / "alias.toml")
    before = source.read_bytes()
    manifest = manifest_file(
        tmp_path, [("one", "doc.odt", "plan.toml"), ("two", "doc.odt", "alias.toml")]
    )
    record = run_batch(manifest, tmp_path / "out", PipelineOptions(profile="inspect"))
    assert record.exit_status == 0
    assert source.read_bytes() == before
    assert plan.read_bytes() == (tmp_path / "alias.toml").read_bytes()


def test_execution_and_publication_failures_do_not_stop_later_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = importlib.import_module("odfa11y.batch.run")
    original = runner.run_pipeline
    make_minimal_odt(tmp_path / "doc.odt")
    (tmp_path / "plan.toml").write_text('[document]\ntitle="T"\nlanguage="en"')
    manifest = manifest_file(
        tmp_path, [(name, "doc.odt", "plan.toml") for name in ("broken", "valid")]
    )

    def failing_pipeline(
        source: str | Path,
        operations: Sequence[Operation],
        policy: FidelityPolicy,
        output_dir: str | Path,
        options: PipelineOptions | None = None,
    ) -> RunRecord:
        if str(output_dir).endswith("broken"):
            msg = "PRIVATE /private/host/path"
            raise OSError(msg)
        return original(source, operations, policy, output_dir, options)

    monkeypatch.setattr(runner, "run_pipeline", failing_pipeline)
    record = run_batch(manifest, tmp_path / "out", PipelineOptions(profile="inspect"))
    assert [item["exit_status"] for item in record.items] == [3, 0]
    assert record.items[0]["failed_stage"] == "pipeline"
    assert check_bundle(tmp_path / "out" / "broken") == []
    assert "PRIVATE" not in (tmp_path / "out" / "broken" / "run.json").read_text()


def test_aggregate_precedence_and_atomic_summary_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = BatchRecord(items=[{"id": "one", "status": "failed", "exit_status": 1}])
    record.publish(tmp_path)
    previous = (tmp_path / "batch.json").read_bytes()
    original = Path.replace

    def failed_replace(path: Path, destination: str | Path) -> Path:
        if str(destination).endswith("batch.json"):
            msg = "publication failed"
            raise OSError(msg)
        return original(path, destination)

    record.items.append({"id": "two", "status": "failed", "exit_status": 2})
    assert record.exit_status == 2
    record.items.append({"id": "three", "status": "failed", "exit_status": 3})
    assert record.exit_status == 3
    monkeypatch.setattr(Path, "replace", failed_replace)
    with pytest.raises(OSError, match="publication"):
        record.publish(tmp_path)
    assert (tmp_path / "batch.json").read_bytes() == previous
    assert [path.name for path in tmp_path.iterdir()] == ["batch.json"]


def test_unpublishable_item_is_explicit_and_later_document_still_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = importlib.import_module("odfa11y.batch.run")
    make_minimal_odt(tmp_path / "doc.odt")
    (tmp_path / "plan.toml").write_text('[document]\ntitle="T"\nlanguage="en"')
    manifest = manifest_file(
        tmp_path, [("failed", "doc.odt", "missing.toml"), ("valid", "doc.odt", "plan.toml")]
    )

    def unavailable_bundle(*_args: object, **_kwargs: object) -> None:
        msg = "output filesystem is unavailable"
        raise OSError(msg)

    monkeypatch.setattr(runner, "write_bundle", unavailable_bundle)
    record = run_batch(manifest, tmp_path / "out", PipelineOptions(profile="inspect"))
    assert record.items[0] == {
        "id": "failed",
        "status": "failed",
        "exit_status": 3,
        "failed_stage": "publish-evidence",
        "evidence": None,
    }
    assert record.items[1]["exit_status"] == 0
    assert check_bundle(tmp_path / "out" / "valid") == []
