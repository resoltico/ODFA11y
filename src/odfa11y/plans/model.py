# SPDX-License-Identifier: MPL-2.0
"""Source-bound plans of answered human decisions and fidelity policy."""

import hashlib
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Literal
lazy from collections.abc import Iterable

from odfa11y.contracts import Description, Length, Pattern, record_dict, validate
from odfa11y.errors import PackageError, PlanError
from odfa11y.plans.fidelity import FidelityPolicy, Pagination
lazy from odfa11y.contracts import JsonObject
lazy from odfa11y.decisions import Decision
lazy from odfa11y.plans.contracts import to_file

SOURCE_SHA256_PATTERN = r"^[0-9a-f]{64}(?![\s\S])"
PLAN_SCHEMA_VERSION = 1
HASH_CHUNK_BYTES = 1 << 20


@dataclass(frozen=True, slots=True)
class SourceBinding:
    """Exact physical source bytes to which human decisions were bound."""

    sha256: Annotated[
        str, Pattern(SOURCE_SHA256_PATTERN), Description("SHA-256 of the reviewed source bytes.")
    ]


@dataclass(frozen=True, slots=True)
class PlanHeader:
    """The plan format, exact source binding and generator version."""

    schema_version: Literal[1]
    source: SourceBinding
    generator: Annotated[str, Length(minimum=1), Description("Version that generated the plan.")]


@dataclass(frozen=True, slots=True)
class Plan:
    """A bound set of answers, with no legacy configuration or operation-list form."""

    header: PlanHeader
    decisions: tuple[Decision, ...] = ()
    fidelity: FidelityPolicy = field(default_factory=Pagination.SAME)

    def __post_init__(self) -> None:
        """Reject conflicting duplicate answers before execution.

        Raises
        ------
        PlanError
            More than one answer addresses the same kind and target.

        """
        validate(self.header, label="plan", error=PlanError)
        validate(self.fidelity, label="fidelity", error=PlanError)
        keys = [
            (answer.kind.id, answer.target.path if answer.target else None)
            for answer in self.decisions
        ]
        if len(keys) != len(set(keys)):
            msg = "A plan cannot answer the same decision kind and target twice"
            raise PlanError(msg)

    @classmethod
    def _decoded(
        cls, header: PlanHeader, decisions: tuple[Decision, ...], fidelity: FidelityPolicy
    ) -> Plan:
        keys = [
            (decision.kind.id, decision.target.path if decision.target else None)
            for decision in decisions
        ]
        if len(keys) != len(set(keys)):
            message = "A plan cannot answer the same decision kind and target twice"
            raise PlanError(message)
        result = object.__new__(cls)
        object.__setattr__(result, "header", header)
        object.__setattr__(result, "decisions", decisions)
        object.__setattr__(result, "fidelity", fidelity)
        return result

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
            PlanHeader(
                PLAN_SCHEMA_VERSION, SourceBinding(source_digest(Path(source))), version("odfa11y")
            ),
            tuple(decisions),
            fidelity or Pagination.SAME(),
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
        return record_dict(to_file(self))


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
