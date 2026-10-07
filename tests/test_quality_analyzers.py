# SPDX-License-Identifier: MPL-2.0
"""Real analyzers detect authored-path counterexamples instead of trusting discovery claims."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from odfa11y.external_tools import run_bounded
from tools import check_quality

ROOT = Path(__file__).resolve().parents[1]


def test_ruff_checks_nested_hidden_and_ignored_authored_code_but_skips_root_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ruff = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["ruff"]
    config = tmp_path / "pyproject.toml"
    config.write_text(
        "[tool.ruff]\npreview = true\nrespect-gitignore = false\nexclude = "
        + json.dumps(ruff["exclude"])
        + '\n[tool.ruff.lint]\nselect = ["complex-structure"]\n'
        + "[tool.ruff.lint.mccabe]\nmax-complexity = "
        + str(ruff["lint"]["mccabe"]["max-complexity"])
        + "\n"
    )
    source = (
        "def complex_function(value):\n"
        + "".join(
            f"    if value == {i}:\n        value += {i}\n"
            for i in range(ruff["lint"]["mccabe"]["max-complexity"] + 1)
        )
        + "    return value\n"
    )
    checked = ["src/domain/dist", "src/domain/build", ".vscode", ".ignored"]
    for name in [*checked, "build", "dist", ".venv"]:
        directory = tmp_path / name
        directory.mkdir(parents=True)
        (directory / "counterexample.py").write_text(source)
    (tmp_path / ".gitignore").write_text(".ignored/\n")
    monkeypatch.chdir(tmp_path)
    command = [sys.executable, "-m", "ruff"]
    result = run_bounded([*command, "check", "--config", str(config), str(tmp_path)], timeout=20)
    assert result.returncode == 1
    for directory in checked:
        assert f" --> {Path(directory) / 'counterexample.py'}:" in result.stdout
    for directory in ("build", "dist", ".venv"):
        assert f" --> {Path(directory) / 'counterexample.py'}:" not in result.stdout
    (tmp_path / "src/domain/dist/counterexample.py").write_text("value=1\n")
    formatted = run_bounded(
        [*command, "format", "--check", "--config", str(config), str(tmp_path)], timeout=20
    )
    assert formatted.returncode == 1
    assert str(Path("src/domain/dist/counterexample.py")) in formatted.stdout + formatted.stderr


@pytest.mark.parametrize("directory", ["src/domain/dist", ".vscode", ".ignored"])
def test_type_gate_uses_explicit_authored_inputs(tmp_path: Path, directory: str) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.ruff.lint]\nselect=["ALL"]\n[tool.ty.src]\ninclude=["src", "tests", "tools"]\n'
    )
    (tmp_path / ".gitignore").write_text(".ignored/\n")
    target = tmp_path / directory
    target.mkdir(parents=True)
    (target / "counterexample.py").write_text('value: int = "wrong type"\n')
    assert check_quality.check_types(tmp_path) == 1
    (target / "counterexample.py").write_text("value: int = 1\n")
    for name in ("build", "dist", ".venv"):
        generated = tmp_path / name
        generated.mkdir()
        (generated / "generated.py").write_text('value: int = "wrong type"\n')
    assert check_quality.check_types(tmp_path) == 0


def test_type_gate_rejects_empty_discovery_and_unavailable_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text('[tool.ruff.lint]\nselect=["ALL"]\n[tool.ty]\n')
    assert check_quality.check_types(tmp_path) == 1
    (tmp_path / "valid.py").write_text("value: int = 1\n")
    monkeypatch.setattr(check_quality.sys, "executable", str(tmp_path / "missing-python"))
    assert check_quality.check_types(tmp_path) == 1


def test_type_gate_preserves_analyzer_failure_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text('[tool.ruff.lint]\nselect=["ALL"]\n[tool.ty]\n')
    (tmp_path / "valid.py").write_text("value: int = 1\n")
    monkeypatch.setattr(
        check_quality.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=7)
    )
    assert check_quality.check_types(tmp_path) == 7


def test_type_gate_rejects_missing_authoritative_configuration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "valid.py").write_text("value: int = 1\n")
    assert check_quality.check_types(tmp_path) == 1
    assert "Cannot read authoritative analyzer configuration" in capsys.readouterr().err
