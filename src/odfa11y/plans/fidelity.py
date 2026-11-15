# SPDX-License-Identifier: MPL-2.0
"""Closed fidelity policies make ignored pagination settings unrepresentable."""

from dataclasses import dataclass, field
from typing import Annotated, Literal

from odfa11y.contracts import Description, Range, decode, record_dict
from odfa11y.contracts.types import JsonObject
from odfa11y.errors import PlanError


@dataclass(frozen=True, slots=True)
class SamePagination:
    """Keep page geometry and compare rendered ink as well as text and links."""

    raster_tolerance: Annotated[
        float, Range(minimum=0), Description("Largest permitted changed-ink ratio.")
    ] = 0.15
    ink_threshold: Annotated[
        int, Range(0, 255), Description("Luminance below which a rendered pixel is ink.")
    ] = 200
    pagination: Literal["same"] = field(default="same", init=False)

    def as_dict(self) -> JsonObject:
        return record_dict(self)


@dataclass(frozen=True, slots=True)
class MayChangePagination:
    """Allow page layout changes while preserving text and links."""

    pagination: Literal["may-change"] = field(default="may-change", init=False)

    def as_dict(self) -> JsonObject:
        return record_dict(self)


type FidelityPolicy = SamePagination | MayChangePagination


class Pagination:
    """Construct the two supported fidelity policies."""

    MAY_CHANGE = MayChangePagination()

    @staticmethod
    def SAME(raster_tolerance: float = 0.15, ink_threshold: int = 200) -> SamePagination:
        return decode(
            SamePagination,
            {"raster_tolerance": raster_tolerance, "ink_threshold": ink_threshold},
            label="fidelity",
            error=PlanError,
        )
