# SPDX-License-Identifier: MPL-2.0
"""Parser nesting and named dependency nesting must not multiply Python stack depth."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

import pytest

from odfa11y.errors import ToolFailedError
from odfa11y.native.formula_syntax import OPENFORMULA, FormulaFacts, classify_formula
from odfa11y.native.process import run_bounded
from odfa11y.odf import OdfDocument, validate
from odfa11y.pdf.fidelity import FidelityPolicy
from odfa11y.pipeline.context import RunSettings
from odfa11y.pipeline.engine import execute
from odfa11y.pipeline.native import export_document
from odfa11y.pipeline.profiles import profile_named
from odfa11y.report import FactKeys
from odfa11y.source_audit import audit_odf

from .documents import TABLE_BODY, Variant, make_flat
from .reviewed_plans import reviewed_plan

if TYPE_CHECKING:
    from pathlib import Path


def named_chain(tmp_path: Path, count: int, wrappers: int) -> Path:
    names = []
    for index in range(count):
        target = "1" if index == count - 1 else f"Chain_{index + 1}"
        formula = "of:=" + "SUM(" * wrappers + target + ")" * wrappers
        names.append(
            f'<table:named-expression table:name="Chain_{index}" '
            f'table:base-cell-address="$Sheet1.$A$1" table:expression="{formula}"/>'
        )
    body = (
        f'<office:spreadsheet xmlns:of="{OPENFORMULA}">{TABLE_BODY}'
        f"<table:named-expressions>{''.join(names)}</table:named-expressions>"
        "</office:spreadsheet>"
    )
    source = make_flat(tmp_path, "spreadsheet", Variant(body=body))
    # Independent normative input oracle; there is no malformed-schema escape hatch.
    assert validate(OdfDocument.open(source)).count == 0
    return source


@pytest.mark.parametrize(("count", "wrappers"), [(10, 1), (40, 8)])
def test_valid_named_chains_do_not_multiply_lexical_parser_stack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int, wrappers: int
) -> None:
    source = named_chain(tmp_path, count, wrappers)
    report = audit_odf(source)
    assert "NATIVE001" not in {finding.rule_id for finding in report.findings}
    calls = []
    monkeypatch.setattr("odfa11y.pipeline.native.export_pdfua", lambda *args: calls.append(args))
    export_document(source, tmp_path / "output.pdf")
    assert len(calls) == 1


def test_name_depth_budget_is_an_explicit_refusal_through_all_public_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = named_chain(tmp_path, 80, 8)
    original = source.read_bytes()
    report = audit_odf(source)
    assert "NATIVE001" in {finding.rule_id for finding in report.findings}
    assert report.facts[FactKeys.NATIVE_LIMITATIONS]["formula_incomplete"] > 0
    calls = []
    monkeypatch.setattr("odfa11y.pipeline.native.export_pdfua", lambda *args: calls.append(args))
    with pytest.raises(ToolFailedError, match="formula context"):
        export_document(source, tmp_path / "output.pdf")
    record = execute(
        source,
        reviewed_plan(source, [], FidelityPolicy()),
        tmp_path / "evidence",
        RunSettings(profile=profile_named("verify")),
    )
    assert record.failed_stage == "export-source"
    assert record.exit_status == 3
    assert calls == []
    assert not (tmp_path / "output.pdf").exists()
    assert source.read_bytes() == original
    command = [sys.executable, "-m", "odfa11y", "audit", str(source), "--format", "json"]
    completed = run_bounded(command, timeout=30)
    assert "RecursionError" not in completed.stderr
    assert completed.returncode in {0, 1, 2}
    payload = json.loads(completed.stdout)
    assert "NATIVE001" in {finding["rule_id"] for finding in payload["findings"]}


def test_remaining_python_stack_exhaustion_is_explicitly_incomplete() -> None:
    def unavailable_stack(_: str) -> FormulaFacts:
        message = "Caller stack exhausted"
        raise RecursionError(message)

    assert classify_formula("of:=Named", {"of": OPENFORMULA}, unavailable_stack) == FormulaFacts(
        incomplete=1
    )
