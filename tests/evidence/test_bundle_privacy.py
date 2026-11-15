# SPDX-License-Identifier: MPL-2.0
"""Diagnostic evidence redacts local directories on successful and failed runs."""

import stat
import sys
lazy from pathlib import Path

import pytest

from odfa11y.application.tools import Tools
from odfa11y.evidence import check_bundle
from odfa11y.evidence.redact import ABSOLUTE_PATH
from odfa11y.plans.fidelity import Pagination
from odfa11y.run.context import RunSettings
from odfa11y.run.engine import execute
from tests.fixtures.answers import (
    graphic_answer,
    graphic_inputs,
    metadata_input,
)
from tests.fixtures.plans import reviewed_plan
from tests.fixtures.writer import make_minimal_odt

SENTINEL = "zz-private-person-zz"
DIAGNOSTIC_NAMES = {"run.json", "REVIEW.md", "verapdf.xml", "manifest.json"}
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="uses shell-script stand-ins")


def assert_path_free(bundle: Path, tmp_path: Path) -> None:
    """Fail if a generated diagnostic mentions a local path or sentinel directory."""
    assert check_bundle(bundle) == []
    for path in bundle.rglob("*"):
        if path.name not in DIAGNOSTIC_NAMES:
            continue
        text = path.read_text(encoding="utf-8")
        assert SENTINEL not in text, path.name
        assert str(tmp_path) not in text, path.name
        assert not ABSOLUTE_PATH.search(text), (path.name, ABSOLUTE_PATH.search(text))


def workspace(tmp_path: Path) -> Path:
    """Create a nested, identifiable directory to work in.

    Returns
    -------
    Path
        The directory.

    """
    directory = tmp_path / SENTINEL / "documents"
    directory.mkdir(parents=True)
    return directory


def stand_in(directory: Path, body: str, name: str = "fake-soffice") -> Path:
    """Write an executable shell script.

    Returns
    -------
    Path
        The script path.

    """
    path = directory / name
    version = 'if [ "$1" = "--version" ]; then echo "LibreOffice 26.8.0.3"; exit 0; fi'
    path.write_text(f"#!/bin/sh\n{version}\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def run(directory: Path, options: RunSettings, source: Path | None = None) -> Path:
    """Run a pipeline whose paths all contain the sentinel and return its bundle.

    Returns
    -------
    Path
        The evidence directory.

    """
    source = source or make_minimal_odt(directory / "input.odt")
    out = directory / "evidence"
    execute(
        source, reviewed_plan(source, [metadata_input(title="T")], Pagination.SAME()), out, options
    )
    return out


def test_a_missing_tool_path_is_not_leaked(tmp_path: Path) -> None:
    directory = workspace(tmp_path)
    options = RunSettings(tools=Tools(soffice=str(directory / "no-such-soffice")))
    assert_path_free(run(directory, options), tmp_path)


@posix_only
def test_a_non_executable_tool_path_is_not_leaked(tmp_path: Path) -> None:
    directory = workspace(tmp_path)
    plain = directory / "soffice"
    plain.write_text("not a program", encoding="utf-8")
    assert_path_free(run(directory, RunSettings(tools=Tools(soffice=str(plain)))), tmp_path)


@posix_only
def test_a_failing_tool_that_prints_every_argument_is_not_leaked(tmp_path: Path) -> None:
    directory = workspace(tmp_path)
    tool = stand_in(directory, 'echo "args: $@" >&2; echo "out: $@"; exit 1')
    bundle = run(directory, RunSettings(tools=Tools(soffice=str(tool))))
    assert_path_free(bundle, tmp_path)
    stage = next(
        s
        for s in __import__("json").loads((bundle / "run.json").read_text())["stages"]
        if s["name"] == "export-source"
    )
    assert "exit status 1" in stage["reason"]
    assert "args:" in stage["details"]  # the diagnostic survives, minus the paths


@posix_only
def test_a_tool_that_succeeds_without_output_is_not_leaked(tmp_path: Path) -> None:
    directory = workspace(tmp_path)
    tool = stand_in(directory, "exit 0")
    assert_path_free(run(directory, RunSettings(tools=Tools(soffice=str(tool)))), tmp_path)


def test_an_unreadable_source_is_not_leaked(tmp_path: Path) -> None:
    directory = workspace(tmp_path)
    bundle = run(directory, RunSettings(), source=directory / "absent.odt")
    assert_path_free(bundle, tmp_path)


def test_a_damaged_source_is_not_leaked(tmp_path: Path) -> None:
    directory = workspace(tmp_path)
    broken = directory / "broken.odt"
    broken.write_bytes(b"not a zip")
    assert_path_free(run(directory, RunSettings(), source=broken), tmp_path)


def test_a_failed_plan_is_not_leaked(tmp_path: Path) -> None:
    directory = workspace(tmp_path)
    source = make_minimal_odt(directory / "input.odt")
    out = directory / "evidence"
    plan = [graphic_inputs({"Missing": graphic_answer("x")})]
    execute(source, reviewed_plan(source, plan, Pagination.SAME()), out, RunSettings())
    assert_path_free(out, tmp_path)
