# SPDX-License-Identifier: AGPL-3.0-only
"""Exercise validated edit inputs and inject faults into the actual decision executor."""

import re
from collections.abc import Sequence
from pathlib import Path

from odfa11y.application.remediate import finish_candidate, remediate
from odfa11y.odf import OdfDocument
from odfa11y.remediate import RemediationResult
from odfa11y.remediate.execute import execute_decisions, require_remediable
from tests.fixtures.answers import Authored, contains_fault, materialize
from tests.fixtures.plans import reviewed_plan


def apply_answers(
    source: str | Path,
    destination: str | Path,
    inputs: Sequence[Authored],
    *,
    dry_run: bool = False,
) -> RemediationResult:
    """Use the application path except for explicitly injected unregistered fault callbacks."""
    source, destination = Path(source), Path(destination)
    if contains_fault(inputs):
        document = OdfDocument.open(source)
        require_remediable(document, source)
        candidate = execute_decisions(document, source, materialize(document, inputs))
        return finish_candidate(
            candidate, source, destination, dry_run=dry_run, replace_existing=True
        )
    return remediate(
        source, destination, reviewed_plan(source, inputs), dry_run=dry_run, replace=True
    )


def assert_refused(result: RemediationResult, *, match: str | None = None) -> str:
    """Require a structured failure and preserve existing diagnostic assertions.

    Returns
    -------
    str
        The actual structured messages, for assertions covering multiple failed targets.

    """
    assert not result.published
    assert result.exit_status == 2
    assert result.violations
    text = "\n".join(
        f"{violation.kind_id or ''} [{violation.target or ''}]: {violation.message}"
        for violation in result.violations
    )
    if match is not None:
        assert re.search(match, text), text
    return text
