# SPDX-License-Identifier: MPL-2.0
"""How strictly a candidate render must match its source render."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from odfa11y.errors import ConfigError

MAX_CHANNEL_VALUE = 255
PAGINATION_MODES = ("same", "may-change")


@dataclass(frozen=True, slots=True)
class FidelityPolicy:
    """Comparison rules; defaults demand identical pagination and unmoved page content.

    A pixel is *ink* when its luminance is below ``ink_threshold`` (0-255). A page differs by
    the fraction of its ink that is present in only one render, so moved content scores high
    while a colour change or an underline scores low. ``raster_tolerance`` is the largest
    fraction allowed per page; the default sits between measured link-styling changes
    (about 3-9%) and a two-line layout shift (over 100%).
    """

    pagination: str = "same"
    raster_tolerance: float = 0.15
    ink_threshold: int = 200
    dpi: int = 72

    def __post_init__(self) -> None:
        """Validate policy before any comparison work.

        Raises
        ------
        ConfigError
            A field has an unsupported type, range or nonfinite value.

        """
        if self.pagination not in PAGINATION_MODES:
            msg = f"fidelity.pagination must be one of {', '.join(PAGINATION_MODES)}"
            raise ConfigError(msg)
        tolerance = self.raster_tolerance
        try:
            finite = isinstance(tolerance, (int, float)) and math.isfinite(tolerance)
        except OverflowError:
            finite = False
        if isinstance(tolerance, bool) or not finite or tolerance < 0:
            msg = "fidelity.raster_tolerance must be a finite non-negative number"
            raise ConfigError(msg)
        if type(self.ink_threshold) is not int or not 0 <= self.ink_threshold <= MAX_CHANNEL_VALUE:
            msg = "fidelity.ink_threshold must be an integer 0-255"
            raise ConfigError(msg)
        if type(self.dpi) is not int or self.dpi < 1:
            msg = "fidelity.dpi must be a positive integer"
            raise ConfigError(msg)

    def as_dict(self) -> dict[str, Any]:
        """Serialize the policy.

        Returns
        -------
        dict[str, Any]
            The policy fields.

        """
        return asdict(self)
