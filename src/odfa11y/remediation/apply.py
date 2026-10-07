# SPDX-License-Identifier: MPL-2.0
"""Apply operations to a document under the postconditions that make a run safe to publish."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from odfa11y.errors import OutputError, RemediationError
from odfa11y.odf import OdtDocument, regressions, text_is_preserved, validate

from .outcome import RemediationResult, Status
from .spacers import RemoveEmptySpacers

if TYPE_CHECKING:
    from collections.abc import Sequence

    from odfa11y.odf import SchemaResult

    from .outcome import Operation, Outcome


def remediate(
    source: str | Path,
    destination: str | Path,
    operations: Sequence[Operation],
    *,
    dry_run: bool = False,
) -> RemediationResult:
    """Apply operations in order and publish the result only if every postcondition holds.

    Postconditions: no operation failed, visible text is preserved (apart from counted
    spacer removals), and the ODF schema reports no violation that the source did not
    already have. On any failure nothing is written.

    Returns
    -------
    RemediationResult
        The per-target outcomes; ``destination`` is None for a dry run.

    Raises
    ------
    RemediationError
        An operation failed, text changed, or the schema check regressed.

    """
    source, destination = Path(source), Path(destination)
    _require_distinct(source, destination)
    document = OdtDocument.open(source)
    text_before = document.text_snapshot()
    schema_before = validate(document)

    outcomes: list[Outcome] = []
    for operation in operations:
        edits_before = document.edit_count
        produced = operation.apply(document)
        _check_edit_accounting(operation, produced, document.edit_count - edits_before)
        outcomes.extend(produced)
    failures = [o for o in outcomes if o.status is Status.FAILED]
    if failures:
        lines = [f"{o.operation}{f' [{o.key}]' if o.key else ''}: {o.message}" for o in failures]
        msg = "Remediation failed; nothing was written:\n" + "\n".join(lines)
        raise RemediationError(msg)

    removed = sum(o.count for o in outcomes if o.operation == RemoveEmptySpacers.name)
    if not text_is_preserved(text_before, document.text_snapshot(), removed_empty_blocks=removed):
        msg = "Visible document text changed during remediation; nothing was written."
        raise RemediationError(msg)
    schema_check = _schema_check(schema_before, validate(document))

    if not dry_run:
        document.save(destination)
    return RemediationResult(
        source=source,
        destination=None if dry_run else destination,
        outcomes=tuple(outcomes),
        schema_check=schema_check,
        dry_run=dry_run,
        operations=tuple(operation.as_dict() for operation in operations),
    )


def _require_distinct(source: Path, destination: Path) -> None:
    same = source.resolve() == destination.resolve() or (
        destination.exists() and source.exists() and Path(source).samefile(destination)
    )
    if same:
        msg = f"Destination must differ from the source: {destination}"
        raise OutputError(msg)


def _check_edit_accounting(operation: Operation, outcomes: Sequence[Outcome], edits: int) -> None:
    applied = any(o.status is Status.APPLIED for o in outcomes)
    if applied != (edits > 0) and not any(o.status is Status.FAILED for o in outcomes):
        msg = (
            f"Internal error: operation {operation.name!r} reported "
            f"{'a change' if applied else 'no change'} but made {edits} edit(s)."
        )
        raise RemediationError(msg)


def _schema_check(before: SchemaResult, after: SchemaResult) -> str:
    if not (before.available and after.available):
        return "skipped: no bundled schema for the source or result version"
    new = regressions(before, after)
    if new:
        lines = [f"{member}: {message}" for member, messages in new.items() for message in messages]
        msg = "Remediation introduced ODF schema violations; nothing was written:\n" + "\n".join(
            lines
        )
        raise RemediationError(msg)
    return f"no new violations against ODF {after.version} ({before.count} pre-existing)"
