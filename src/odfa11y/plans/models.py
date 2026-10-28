# SPDX-License-Identifier: MPL-2.0
"""Source-bound plans of answered human decisions and fidelity policy."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from odfa11y.decisions import validate_answer
from odfa11y.errors import PackageError, PlanError
from odfa11y.pdf.fidelity import FidelityPolicy
from odfa11y.serialization import record_dict

if TYPE_CHECKING:
    from collections.abc import Iterable

    from odfa11y.decisions import Decision
    from odfa11y.serialization import JsonObject

SOURCE_SHA256_PATTERN = r"^[0-9a-f]{64}(?![\s\S])"
PLAN_FORMAT = 1
HASH_CHUNK_BYTES = 1 << 20


@dataclass(frozen=True, slots=True)
class SourceBinding:
    """Exact physical source bytes to which human decisions were bound."""

    sha256: str = field(
        metadata={
            "schema": {
                "pattern": SOURCE_SHA256_PATTERN,
                "description": "SHA-256 of the reviewed source bytes.",
            }
        }
    )

    def __post_init__(self) -> None:
        """Validate bindings created by Python callers as well as the parser."""
        validate_answer(self, "plan.source")


@dataclass(frozen=True, slots=True)
class PlanHeader:
    """The plan format, exact source binding and generator version."""

    format: Literal[1]
    source: SourceBinding
    generator: str = field(
        metadata={"schema": {"minLength": 1, "description": "Version that generated the plan."}}
    )

    def __post_init__(self) -> None:
        """Validate the complete binding envelope."""
        validate_answer(self, "plan")


@dataclass(frozen=True, slots=True)
class Plan:
    """A bound set of answers, with no legacy configuration or operation-list form."""

    header: PlanHeader
    decisions: tuple[Decision, ...] = ()
    fidelity: FidelityPolicy = field(default_factory=FidelityPolicy)

    def __post_init__(self) -> None:
        """Reject conflicting duplicate answers before execution.

        Raises
        ------
        PlanError
            More than one answer addresses the same kind and target.

        """
        keys = [
            (answer.kind.id, answer.target.path if answer.target else None)
            for answer in self.decisions
        ]
        if len(keys) != len(set(keys)):
            msg = "A plan cannot answer the same decision kind and target twice"
            raise PlanError(msg)

    @classmethod
    def for_source(
        cls,
        source: str | Path,
        decisions: Iterable[Decision] = (),
        *,
        fidelity: FidelityPolicy | None = None,
    ) -> Plan:
        """Bind programmatically reviewed decisions to the current source.

        Returns
        -------
        Plan
            A plan with a mandatory source header.

        """
        return cls(
            PlanHeader(PLAN_FORMAT, SourceBinding(source_digest(Path(source))), version("odfa11y")),
            tuple(decisions),
            fidelity or FidelityPolicy(),
        )

    def verify_source(self, source: str | Path, *, rebind: bool = False) -> None:
        """Refuse applying reviewed decisions to different bytes without explicit rebinding.

        Raises
        ------
        PlanError
            The selected source differs from the reviewed source and rebind is false.

        """
        if type(rebind) is not bool:
            msg = "rebind must be an explicit boolean"
            raise PlanError(msg)
        if source_digest(Path(source)) != self.header.source.sha256 and not rebind:
            msg = "Plan/source digest mismatch; review the source and explicitly rebind to proceed."
            raise PlanError(msg)

    def as_dict(self) -> JsonObject:
        """Project the plan into the same tables used by its TOML file.

        Returns
        -------
        JsonObject
            The binding header, answered decision tables and fidelity policy.

        Raises
        ------
        PlanError
            A kind mixes incompatible document and target answer tables.

        """
        tables: dict[str, object] = {}
        for decision in self.decisions:
            answer = {
                key: value
                for key, value in record_dict(decision.answer).items()
                if value is not None
            }
            if decision.target is None:
                tables[decision.kind.id] = answer
            else:
                group = tables.setdefault(decision.kind.id, {})
                if not isinstance(group, dict):
                    msg = "A kind cannot mix document and target answers"
                    raise PlanError(msg)
                group[decision.target.path] = {"fingerprint": decision.fingerprint, **answer}
        return record_dict({
            "plan": record_dict(self.header),
            "decisions": tables,
            "fidelity": record_dict(self.fidelity),
        })


def source_digest(source: Path) -> str:
    """Hash a regular source incrementally without loading another full file copy.

    Returns
    -------
    str
        SHA-256 of the physical input bytes.

    Raises
    ------
    PackageError
        The selected source is not a regular file.

    """
    if not source.is_file():
        msg = "A plan source must be a readable regular file"
        raise PackageError(msg)
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        while chunk := stream.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()
