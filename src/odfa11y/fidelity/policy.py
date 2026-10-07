# SPDX-License-Identifier: MPL-2.0
"""How strictly a candidate render must match its source render."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

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

    def as_dict(self) -> dict[str, Any]:
        """Serialize the policy.

        Returns
        -------
        dict[str, Any]
            The policy fields.

        """
        return asdict(self)
