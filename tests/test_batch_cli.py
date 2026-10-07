# SPDX-License-Identifier: MPL-2.0
"""The public batch command uses ordinary pipeline options and exit statuses."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from odfa11y.cli import main

from .fixtures import make_minimal_odt
from .test_batch import manifest_file

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_batch_cli_publishes_json_and_returns_aggregate_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make_minimal_odt(tmp_path / "doc.odt")
    (tmp_path / "plan.toml").write_text('[document]\ntitle="T"\nlanguage="en"')
    manifest = manifest_file(
        tmp_path, [("valid", "doc.odt", "plan.toml"), ("bad", "missing.odt", "plan.toml")]
    )
    status = main([
        "batch",
        str(manifest),
        "--output-dir",
        str(tmp_path / "out"),
        "--profile",
        "inspect",
        "--format",
        "json",
    ])
    assert status == 3
    captured = capsys.readouterr()
    assert not captured.err
    summary = json.loads(captured.out)
    assert summary == json.loads((tmp_path / "out" / "batch.json").read_text())
    assert summary["status"] == "failed"
    assert summary["items"][0]["status"] == "completed"
    assert str(tmp_path) not in captured.out


def test_batch_cli_text_and_global_validation_have_documented_statuses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = manifest_file(tmp_path, [("one", "missing.odt", "missing.toml")])
    args = ["batch", str(manifest), "--output-dir", str(tmp_path / "out"), "--profile", "inspect"]
    assert main(args) == 3
    text = capsys.readouterr().out
    assert "Batch: failed" in text
    assert "one: failed" in text
    assert "evidence=one" in text
    assert main(args) == 3
    assert "must not exist" in capsys.readouterr().err
