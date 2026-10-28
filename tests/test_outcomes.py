# SPDX-License-Identifier: MPL-2.0
"""Exit aggregation honors severity across inputs, stages and batch items."""

from __future__ import annotations

from itertools import permutations
from typing import TYPE_CHECKING
lazy from pathlib import Path

import pytest

from odfa11y.batch.record import BatchRecord
from odfa11y.cli import main
from odfa11y.errors import PackageError, PlanError
from odfa11y.outcomes import ExitStatus, combine_statuses
from odfa11y.report import Report, rules

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([], 0),
        ([0, 1], 1),
        ([1, 2], 2),
        ([2, 4], 4),
        ([4, 3], 3),
        ([3, 4], 3),
    ],
)
def test_exit_precedence_is_independent_of_numeric_order(
    statuses: list[int], expected: int
) -> None:
    assert combine_statuses(statuses) == expected
    assert (
        BatchRecord(items=[{"exit_status": status} for status in statuses]).exit_status == expected
    )


def test_every_input_order_retains_execution_failure() -> None:
    for statuses in permutations([0, 1, 2, 4, 3]):
        assert combine_statuses(statuses) == ExitStatus.EXECUTION_FAILURE


@pytest.mark.parametrize("execution_failure", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_multi_input_audit_aggregates_usage_findings_and_execution_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    execution_failure: bool,
    reverse: bool,
) -> None:
    def audit(source: Path, **_options: object) -> Iterator[Report]:
        if source.name == "invalid":
            msg = "Invalid plan or policy"
            raise PlanError(msg)
        if source.name == "unreadable":
            msg = "Unreadable input"
            raise PackageError(msg)
        report = Report(kind="text", subject="source")
        report.add(rules.META001)
        yield report

    monkeypatch.setattr("odfa11y.cli.audit.audit_document", audit)
    sources = ["invalid", "findings"]
    if execution_failure:
        sources.append("unreadable")
    if reverse:
        sources.reverse()
    assert main(["audit", *sources, "--format", "json"]) == (3 if execution_failure else 4)
    captured = capsys.readouterr()
    assert "META001" in captured.out
    assert "Invalid plan or policy" in captured.err
