# SPDX-License-Identifier: MPL-2.0
"""No evidence file may carry a local path, whichever way a run succeeds or fails."""

from __future__ import annotations

import stat
import sys
from typing import TYPE_CHECKING

import pytest

from odfa11y.evidence import check_bundle
from odfa11y.evidence.redact import ABSOLUTE_PATH
from odfa11y.families.text import AltText, SetAltText
from odfa11y.fidelity import FidelityPolicy
from odfa11y.pipeline import PipelineOptions, run_pipeline
from odfa11y.remediation import SetMetadata

from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

SENTINEL = "zz-private-person-zz"
TEXT_SUFFIXES = {".json", ".md", ".xml", ".txt"}
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="uses shell-script stand-ins")


def assert_path_free(bundle: Path, tmp_path: Path) -> None:
    """Fail if any textual bundle file mentions a local path or the sentinel directory."""
    assert check_bundle(bundle) == []
    for path in bundle.rglob("*"):
        if path.suffix not in TEXT_SUFFIXES:
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
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def run(directory: Path, options: PipelineOptions, source: Path | None = None) -> Path:
    """Run a pipeline whose paths all contain the sentinel and return its bundle.

    Returns
    -------
    Path
        The evidence directory.

    """
    source = source or make_minimal_odt(directory / "input.odt")
    out = directory / "evidence"
    run_pipeline(source, [SetMetadata(title="T")], FidelityPolicy(), out, options)
    return out


def test_a_missing_tool_path_is_not_leaked(tmp_path: Path) -> None:
    directory = workspace(tmp_path)
    options = PipelineOptions(soffice=str(directory / "no-such-soffice"))
    assert_path_free(run(directory, options), tmp_path)


@posix_only
def test_a_non_executable_tool_path_is_not_leaked(tmp_path: Path) -> None:
    directory = workspace(tmp_path)
    plain = directory / "soffice"
    plain.write_text("not a program", encoding="utf-8")
    assert_path_free(run(directory, PipelineOptions(soffice=str(plain))), tmp_path)


@posix_only
def test_a_failing_tool_that_prints_every_argument_is_not_leaked(tmp_path: Path) -> None:
    directory = workspace(tmp_path)
    tool = stand_in(directory, 'echo "args: $@" >&2; echo "out: $@"; exit 1')
    bundle = run(directory, PipelineOptions(soffice=str(tool)))
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
    assert_path_free(run(directory, PipelineOptions(soffice=str(tool))), tmp_path)


def test_an_unreadable_source_is_not_leaked(tmp_path: Path) -> None:
    directory = workspace(tmp_path)
    bundle = run(directory, PipelineOptions(), source=directory / "absent.odt")
    assert_path_free(bundle, tmp_path)


def test_a_damaged_source_is_not_leaked(tmp_path: Path) -> None:
    directory = workspace(tmp_path)
    broken = directory / "broken.odt"
    broken.write_bytes(b"not a zip")
    assert_path_free(run(directory, PipelineOptions(), source=broken), tmp_path)


def test_a_failed_plan_is_not_leaked(tmp_path: Path) -> None:
    directory = workspace(tmp_path)
    source = make_minimal_odt(directory / "input.odt")
    out = directory / "evidence"
    plan = [SetAltText({"Missing": AltText("x")})]
    run_pipeline(source, plan, FidelityPolicy(), out, PipelineOptions())
    assert_path_free(out, tmp_path)


@pytest.mark.integration
def test_raw_tool_reports_of_a_real_run_are_not_leaked(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    directory = workspace(tmp_path)
    options = PipelineOptions(
        profile="production",
        soffice=external_tool("soffice", "libreoffice"),
        verapdf_path=external_tool("verapdf"),
    )
    bundle = run(directory, options)
    assert_path_free(bundle, tmp_path)
    assert "<work>/remediated.pdf" in (bundle / "verapdf.xml").read_text(encoding="utf-8")
