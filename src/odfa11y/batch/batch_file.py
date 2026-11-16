# SPDX-License-Identifier: AGPL-3.0-only
"""Parse explicit batch inputs and reject ambiguous destinations before execution."""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from odfa11y.errors import OutputOccupied, PlanError

ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
RESERVED_IDS = frozenset({
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})


@dataclass(frozen=True, slots=True)
class BatchItem:
    """One named source and explicitly selected configuration."""

    id: str
    source: Path
    plan: Path


def load_batch_file(batch_file: Path) -> tuple[BatchItem, ...]:
    """Load a strict batch file with portable, case-insensitively unique IDs.

    Returns
    -------
    tuple[BatchItem, ...]
        Inputs in batch file order, resolved relative to its directory.

    Raises
    ------
    PlanError
        The batch file or an entry is invalid.

    """
    try:
        data = tomllib.loads(batch_file.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeError) as exc:
        msg = "Invalid batch TOML batch file"
        raise PlanError(msg) from exc
    entries = data.get("documents")
    if set(data) != {"documents"} or not isinstance(entries, list) or not entries:
        msg = "Batch batch file must contain a nonempty [[documents]] list only"
        raise PlanError(msg)
    items = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"id", "source", "plan"}:
            msg = "Each batch document must contain exactly id, source and plan"
            raise PlanError(msg)
        identity = entry["id"]
        if (
            not isinstance(identity, str)
            or not ID_PATTERN.fullmatch(identity)
            or identity.upper() in RESERVED_IDS
        ):
            msg = "Batch IDs require 1-64 ASCII letters, digits, underscores or hyphens"
            raise PlanError(msg)
        if identity.casefold() in seen:
            msg = "Batch IDs must be unique ignoring case"
            raise PlanError(msg)
        seen.add(identity.casefold())
        items.append(
            BatchItem(
                identity,
                _input(batch_file.parent, entry["source"]),
                _input(batch_file.parent, entry["plan"]),
            )
        )
    return tuple(items)


def _input(base: Path, value: object) -> Path:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        msg = "Batch source and plan must be nonempty relative paths"
        raise PlanError(msg)
    path = Path(value)
    if path.is_absolute() or re.match(r"^[A-Za-z]:", value) or value.startswith(("/", "\\")):
        msg = "Batch source and plan paths must be relative to the batch file"
        raise PlanError(msg)
    return base / path


def preflight(batch_file: Path, output: Path, items: tuple[BatchItem, ...]) -> None:
    """Reject occupied, aliased or overlapping output paths before any writes.

    Raises
    ------
    OutputOccupied
        The new batch root would touch existing or input data.

    """
    absolute = output.absolute()
    if any(path.is_symlink() for path in (absolute, *absolute.parents)):
        msg = "Batch output and its ancestors must not be symbolic links"
        raise OutputOccupied(msg)
    if absolute.exists():
        msg = "Batch output directory must not exist"
        raise OutputOccupied(msg)
    root = absolute.resolve()
    for path in (batch_file, *(item.source for item in items), *(item.plan for item in items)):
        if path.absolute().is_relative_to(absolute) or path.resolve().is_relative_to(root):
            msg = "Batch output must not contain a batch file, source or plan"
            raise OutputOccupied(msg)
