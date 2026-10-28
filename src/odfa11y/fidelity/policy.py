# SPDX-License-Identifier: MPL-2.0
"""How strictly a candidate render must match its source render."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from odfa11y.errors import PlanError

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

    pagination: str = "same"
    raster_tolerance: float = 0.15
    ink_threshold: int = 200
    dpi: int = 72

    def __post_init__(self) -> None:
        """Validate policy before any comparison work.

        Raises
        ------
        PlanError
            A field has an unsupported type, range or nonfinite value.

        """
        if self.pagination not in PAGINATION_MODES:
            msg = f"fidelity.pagination must be one of {', '.join(PAGINATION_MODES)}"
            raise PlanError(msg)
        tolerance = self.raster_tolerance
        try:
            finite = isinstance(tolerance, (int, float)) and math.isfinite(tolerance)
        except OverflowError:
            finite = False
        if isinstance(tolerance, bool) or not finite or tolerance < 0:
            msg = "fidelity.raster_tolerance must be a finite non-negative number"
            raise PlanError(msg)
        if type(self.ink_threshold) is not int or not 0 <= self.ink_threshold <= MAX_CHANNEL_VALUE:
            msg = "fidelity.ink_threshold must be an integer 0-255"
            raise PlanError(msg)
        if type(self.dpi) is not int or self.dpi < 1:
            msg = "fidelity.dpi must be a positive integer"
            raise PlanError(msg)

    def as_dict(self) -> dict[str, Any]:
        """Serialize the policy.

        Returns
        -------
        dict[str, Any]
            The policy fields.

        """
        return asdict(self)
