# SPDX-License-Identifier: MPL-2.0
"""How strictly a candidate render must match its source render."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from odfa11y.decisions import validate_answer

MAX_CHANNEL_VALUE = 255
PAGINATION_MODES = ("same", "may-change")


@dataclass(frozen=True, slots=True)
class FidelityPolicy:
    """Comparison rules for extracted text, links and optional page/raster checks.

    ``same`` pagination checks page count and geometry, then ink when those match;
    ``may-change`` retains text and link checks. A pixel is ink when its luminance is below
    ``ink_threshold``. For equal-sized rasters, the difference is the exclusive-or ink count
    divided by the larger source/candidate ink count, with a minimum denominator of one.
    The ratio can exceed one; ``raster_tolerance`` is the largest accepted per-page ratio.
    This comparison does not establish logical reading order or accessibility.
    """

    pagination: str = field(
        default="same",
        metadata={
            "schema": {
                "enum": list(PAGINATION_MODES),
                "description": "Require fixed pagination or allow page-layout changes.",
            },
            "error": "must be one of " + ", ".join(PAGINATION_MODES),
        },
    )
    raster_tolerance: float = field(
        default=0.15,
        metadata={
            "schema": {"minimum": 0, "description": "Largest permitted changed-pixel ratio."},
            "error": "must be a finite non-negative number",
        },
    )
    ink_threshold: int = field(
        default=200,
        metadata={
            "schema": {
                "minimum": 0,
                "maximum": MAX_CHANNEL_VALUE,
                "description": "Luminance below which a pixel is ink.",
            },
            "error": f"must be an integer 0-{MAX_CHANNEL_VALUE}",
        },
    )
    dpi: int = field(
        default=72,
        metadata={
            "schema": {"minimum": 1, "description": "Raster comparison resolution."},
            "error": "must be a positive integer",
        },
    )

    def __post_init__(self) -> None:
        """Validate direct callers through the same declarative contract as plan parsing.

        Unsupported fields raise PlanError from the shared answer validator.

        """
        validate_answer(self, "fidelity")
        object.__setattr__(self, "raster_tolerance", float(self.raster_tolerance))

    def as_dict(self) -> dict[str, Any]:
        """Serialize the policy.

        Returns
        -------
        dict[str, Any]
            The policy fields.

        """
        return asdict(self)
