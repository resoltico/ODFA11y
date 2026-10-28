# SPDX-License-Identifier: MPL-2.0
"""The root use cases own continuation, effective policy and native tool selection."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import odfa11y as api
from odfa11y.errors import ToolFailedError
from odfa11y.records import DoctorRecord, Toolchain
from odfa11y.report import rules

from .fixtures import make_minimal_odt
from .pdf_fixtures import text_pdf

if TYPE_CHECKING:
    from collections.abc import Iterator


def test_cli_imports_only_the_root_application_surface() -> None:
    root = Path(__file__).parents[1] / "src/odfa11y/cli"
    for source in root.glob("*.py"):
        for node in ast.walk(ast.parse(source.read_text())):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("odfa11y")
            ):
                assert node.module == "odfa11y", (source, node.module)
            if isinstance(node, ast.Import):
                assert all(not name.name.startswith("odfa11y.") for name in node.names)


def test_multi_input_audit_retains_success_after_execution_failure(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    missing = tmp_path / "missing.odt"
    result = api.audit([missing, source])
    assert len(result.inputs) == 2
    assert isinstance(result.inputs[0].error, FileNotFoundError)
    assert result.inputs[1].error is None
    assert result.exit_status == api.ExitStatus.EXECUTION_FAILURE
    assert len(result.reports) == 1
    serialized = result.as_dict()
    assert serialized["exit_status"] == 3
    inputs = serialized["inputs"]
    assert isinstance(inputs, list)
    first = inputs[0]
    assert isinstance(first, dict)
    assert "error" not in first
    rendered = result.render("json")
    assert rendered is not None
    assert json.loads(rendered)["facts"]["document.title"] == "Synthetic accessible document"


def test_partial_input_reports_survive_later_failure_and_sarif_is_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    failure = ToolFailedError("Controlled validator failure")

    def inspect(source: Path, **_options: object) -> Iterator[api.Report]:
        report = api.Report(kind="pdf", subject=source.name, sources=(source,))
        report.add(rules.PDF005)
        yield report
        raise failure

    monkeypatch.setattr("odfa11y.application.audit_document", inspect)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF")
    result = api.audit(source)
    assert len(result.reports) == 1
    assert result.failures[0].error is failure
    assert result.exit_status == api.ExitStatus.EXECUTION_FAILURE
    assert result.render("json") is not None
    with pytest.raises(ToolFailedError, match="Controlled validator failure"):
        result.render("sarif", source_root=tmp_path)


def test_source_profile_is_a_value_and_needs_no_native_tool(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt")
    prepared = api.plan(source)
    assert prepared.exit_status == api.ExitStatus.PASSED
    assert prepared.template is not None
    plan_path = tmp_path / "review.plan.toml"
    plan_path.write_text(prepared.template)
    result = api.run(
        source,
        plan_path,
        tmp_path / "evidence",
        tools=api.Tools(soffice=tmp_path / "missing"),
        profile=api.PROFILES["source"],
    )
    assert result.exit_status == api.ExitStatus.PASSED
    assert result.profile is api.PROFILES["source"]
    assert result.toolchain.libreoffice is None
    assert api.verify_evidence(tmp_path / "evidence").exit_status == api.ExitStatus.PASSED


def test_compare_and_integrity_results_own_their_status(tmp_path: Path) -> None:
    source = text_pdf(tmp_path / "source.pdf", [["Example"]])
    result = api.compare(source, source)
    assert result.exit_status == api.ExitStatus.PASSED
    assert result.report.passed
    integrity = api.verify_evidence(tmp_path / "missing")
    assert integrity.exit_status == api.ExitStatus.ERRORS
    assert integrity.problems


def test_doctor_retains_controlled_error_and_uses_shared_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = ToolFailedError("Controlled environment failure")
    selected = api.Tools("office", "validator", 7)
    visited = []

    def inspect(tools: api.Tools, **_options: object) -> tuple[DoctorRecord, ToolFailedError]:
        visited.append(tools)
        return DoctorRecord("test", "3.15.2", "test", {}, (), Toolchain()), failure

    monkeypatch.setattr("odfa11y.application.inspect_tools", inspect)
    result = api.doctor(tools=selected)
    assert visited == [selected]
    assert result.error is failure
    assert result.exit_status == api.ExitStatus.EXECUTION_FAILURE
    assert result.as_dict()["exit_status"] == 3
