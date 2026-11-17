# SPDX-License-Identifier: AGPL-3.0-only
"""Collect the decision contracts explicitly declared by document families."""

from typing import cast
lazy from collections.abc import Callable
lazy from pathlib import Path

from odfa11y.contracts.types import format_validators
from odfa11y.errors import PlanError
from odfa11y.families import REGISTRY
from odfa11y.plans.codec import parse_plan
from odfa11y.remediate.document_ops import COMMON_KINDS
lazy from odfa11y.decisions import DecisionKind
lazy from odfa11y.odf import OdfDocument
lazy from odfa11y.plans.model import Plan


def registered_kinds() -> dict[str, DecisionKind]:
    """Collect kinds, refusing conflicting descriptions of a shared identity.

    Returns
    -------
    dict[str, DecisionKind]
        All bundled common/family kinds in canonical registration order.

    Raises
    ------
    PlanError
        Families register incompatible meanings for the same decision identity.

    """
    result = {kind.id: kind for kind in COMMON_KINDS}
    for adapter in REGISTRY.values():
        for kind in adapter.kinds:
            if kind.id in result and result[kind.id] != kind:
                msg = f"Conflicting registrations for decision {kind.id}"
                raise PlanError(msg)
            result[kind.id] = kind
    return dict(sorted(result.items()))


def registered_formats() -> dict[str, Callable[[object], bool]]:
    """Expose the same scalar format checks used by the strict answer codec.

    Returns
    -------
    dict[str, Callable[[str], object]]
        Builtin and family-declared string format validators.

    Raises
    ------
    PlanError
        The same format identity has conflicting validators.

    """
    return cast(
        dict[str, Callable[[object], bool]],
        format_validators(tuple(kind.answer_type for kind in registered_kinds().values())),
    )


def load_plan(
    path: str | Path, *, document: OdfDocument | None = None, source_sha256: str | None = None
) -> Plan:
    """Read a plan using all explicitly registered family contracts.

    Returns
    -------
    Plan
        The strict source-bound plan.

    """
    return parse_plan(path, registered_kinds(), document=document, source_sha256=source_sha256)
