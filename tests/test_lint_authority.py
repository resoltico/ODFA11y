# SPDX-License-Identifier: MPL-2.0
"""Prove missing central policy cannot fall back to permissive analyzer defaults."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

import pytest

from odfa11y.external_tools import run_bounded
from tools.check_quality import check_repository, check_types

if TYPE_CHECKING:
    from pathlib import Path


def test_missing_ruff_policy_does_not_accept_complexity_through_default_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool.odfa11y.quality]\nmax-file-lines = 300\n")
    source = tmp_path / "example.py"
    source.write_text(
        "def choice(value):\n"
        + "".join(f"    if value == {index}:\n        value += {index}\n" for index in range(12))
        + "    return value\n"
    )
    monkeypatch.chdir(tmp_path)
    command = [sys.executable, "-m", "ruff", "check", "--output-format", "json"]
    defaults = run_bounded([*command, "--", str(source)], timeout=20)
    assert defaults.returncode == 0
    assert json.loads(defaults.stdout) == []
    independent = run_bounded([*command, "--select", "C901", "--", str(source)], timeout=20)
    assert independent.returncode == 1
    assert {finding["code"] for finding in json.loads(independent.stdout)} == {"C901"}
    assert any("must select ALL" in error for error in check_repository(tmp_path))
    assert check_types(tmp_path) == 1


@pytest.mark.parametrize("settings", ["", "[tool.ruff]\npreview = true\n"])
def test_missing_rule_selection_is_rejected_even_without_registered_exceptions(
    tmp_path: Path, settings: str
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.odfa11y.quality]\nmax-file-lines = 300\n" + settings
    )
    (tmp_path / "example.py").write_text("value = 1\n")
    assert any("must select ALL" in error for error in check_repository(tmp_path))
