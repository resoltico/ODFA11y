# SPDX-License-Identifier: MPL-2.0
"""Exercise the actual operation engine separately from plan authoring and binding."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.remediation.apply import _document, _execute  # noqa: PLC2701  Test the actual internal engine.

if TYPE_CHECKING:
    from collections.abc import Sequence

    from odfa11y.adapter import Operation
    from odfa11y.remediation import RemediationResult


def execute_operations(
    source: str | Path,
    destination: str | Path,
    operations: Sequence[Operation],
    *,
    dry_run: bool = False,
) -> RemediationResult:
    """Exercise the same guarded engine called after production plan compilation.

    Returns
    -------
    RemediationResult
        Actual outcomes and guard results, not an exception compatibility adapter.

    """
    source, destination = Path(source), Path(destination)
    return _execute(
        _document(source, destination), source, destination, operations, dry_run=dry_run
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
        f"{violation.operation or ''} [{violation.key or ''}]: {violation.message}"
        for violation in result.violations
    )
    if match is not None:
        assert re.search(match, text), text
    return text
