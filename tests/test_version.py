# SPDX-License-Identifier: MPL-2.0
"""Check project, installed metadata and runtime version reporting agree."""

from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path

import pytest

from odfa11y import __version__
from odfa11y.cli import main


def test_project_version_is_installed_and_reported_by_runtime() -> None:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    assert "version" not in project.get("dynamic", [])
    assert project["version"] == importlib.metadata.version(project["name"]) == __version__


def test_cli_reports_installed_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exited:
        main(["--version"])
    assert exited.value.code == 0
    assert capsys.readouterr().out.strip() == f"odfa11y {__version__}"
