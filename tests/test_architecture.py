# SPDX-License-Identifier: MPL-2.0
"""Challenge configured boundaries through the installed Tach CLI."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _check(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tach", "check"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


@pytest.fixture
def architecture_copy(tmp_path: Path) -> Path:
    shutil.copytree(
        ROOT / "src", tmp_path / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    shutil.copyfile(ROOT / "tach.toml", tmp_path / "tach.toml")
    result = _check(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    return tmp_path


@pytest.mark.parametrize(
    ("relative_path", "source", "diagnostic"),
    [
        ("audit/forbidden.py", "from odfa11y.cli import main\n", "cannot depend"),
        (
            "cli/forbidden.py",
            "from odfa11y.audit.engine import audit_odf\n",
            "interface",
        ),
        (
            "families/text/forbidden.py",
            "from odfa11y.families.spreadsheet import ADAPTER\n",
            "cannot depend",
        ),
        (
            "cli/forbidden.py",
            "from odfa11y.families.text import ADAPTER\n",
            "cannot depend",
        ),
        (
            "cli/forbidden.py",
            "from odfa11y.pdf import export_pdfua\n",
            "cannot depend",
        ),
        ("unregistered.py", "from odfa11y.cli import main\n", "cannot depend"),
        ("../unregistered.py", "from odfa11y.cli import main\n", "cannot depend"),
    ],
)
def test_forbidden_dependencies_are_rejected(
    architecture_copy: Path, relative_path: str, source: str, diagnostic: str
) -> None:
    target = architecture_copy / "src" / "odfa11y" / relative_path
    target.write_text(source, encoding="utf-8")
    result = _check(architecture_copy)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert diagnostic in output.lower(), output
    assert "forbidden.py" in output or "unregistered.py" in output, output


def test_declared_dependencies_cannot_authorize_a_cycle(architecture_copy: Path) -> None:
    config = architecture_copy / "tach.toml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            'path = "odfa11y"\ndepends_on = []',
            'path = "odfa11y"\ndepends_on = ["odfa11y.cli"]',
        ),
        encoding="utf-8",
    )
    with (architecture_copy / "src" / "odfa11y" / "__init__.py").open(
        "a", encoding="utf-8"
    ) as stream:
        stream.write("\nfrom odfa11y.cli import main\n")
    result = _check(architecture_copy)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "circular" in output.lower() or "cycle" in output.lower(), output


def test_unused_dependencies_are_rejected(architecture_copy: Path) -> None:
    config = architecture_copy / "tach.toml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            'path = "odfa11y.errors"\ndepends_on = []',
            'path = "odfa11y.errors"\ndepends_on = ["odfa11y.safe_xml"]',
        ),
        encoding="utf-8",
    )
    result = _check(architecture_copy)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "unused" in output.lower(), output
    assert "odfa11y.safe_xml" in output, output


@pytest.mark.parametrize(
    "module",
    [
        "odfa11y.pdf.fidelity",
        "odfa11y.native.link_capability",
        "odfa11y.content",
        "odfa11y.families.text.styles",
        "odfa11y.pipeline",
    ],
)
def test_package_initializers_allow_independent_import_order(module: str) -> None:
    result = subprocess.run(  # noqa: S603  Module names are fixed test parameters and Python is explicit.
        [sys.executable, "-c", f"import {module}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert not result.stdout
