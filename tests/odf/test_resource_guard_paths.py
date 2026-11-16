# SPDX-License-Identifier: MPL-2.0
"""All guarded native entry points refuse offending declarations before application launch."""

from dataclasses import replace
lazy from pathlib import Path

import pytest

from odfa11y.application.native import NativeTools
from odfa11y.cli import main
from odfa11y.evidence import check_bundle
from odfa11y.plans.fidelity import Pagination
from odfa11y.run.context import RunSettings
from odfa11y.run.engine import execute
from odfa11y.run.profiles import profile_named
from tests.fixtures.declarations import declaration
from tests.fixtures.pdf import text_pdf
from tests.fixtures.plans import reviewed_plan
lazy from odfa11y.native.libreoffice import ExportSettings


@pytest.mark.parametrize("kind", ["fill", "bullet", "symbol", "font", "form-image"])
def test_cli_guards_both_compare_operands_and_pipeline_keeps_completed_artifacts(
    native_tools: NativeTools, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    source = declaration(tmp_path, kind, "https://example.test/asset.png")
    safe = declaration(tmp_path, "image", None)
    launched = []

    def export(path: Path, destination: Path, _settings: ExportSettings) -> Path:
        launched.append(path)
        assert path == safe, "unsupported declaration reached native export"
        text_pdf(destination, "Safe operand")
        return destination

    native_tools = replace(native_tools, export=export)
    native_tools = replace(native_tools, export=export)
    native_tools = replace(native_tools, export=export)
    assert (
        main(["export", str(source), str(tmp_path / "export.pdf")], native_tools=native_tools) == 2
    )
    for left, right in [(source, safe), (safe, source)]:
        assert (
            main(["compare", str(left), str(right), "--format", "json"], native_tools=native_tools)
            == 2
        )
    assert launched == [safe]
    output = tmp_path / "evidence"
    record = execute(
        source,
        reviewed_plan(source, [], Pagination.SAME()),
        output,
        RunSettings(profile=profile_named("verify")),
        native_tools=native_tools,
    )
    assert record.failed_stage == "export-source"
    assert record.exit_status == 2
    assert (output / "remediated.odg").read_bytes() == source.read_bytes()
    assert not (output / "source.pdf").exists()
    assert check_bundle(output) == []
    inspected = tmp_path / "source"
    result = execute(
        source,
        reviewed_plan(source, [], Pagination.SAME()),
        inspected,
        RunSettings(profile=profile_named("source")),
        native_tools=native_tools,
    )
    assert result.passed
    assert result.exit_status == 0
    assert (inspected / "remediated.odg").read_bytes() == source.read_bytes()
    assert check_bundle(inspected) == []
    (output / "remediated.odg").write_bytes(b"tampered payload")
    assert check_bundle(output)
