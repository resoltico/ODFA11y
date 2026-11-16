# SPDX-License-Identifier: MPL-2.0
"""Validated portable native-call seconds with one default."""

import math
from typing import ClassVar

from odfa11y.errors import InvalidOption


class Timeout(float):
    DEFAULT: ClassVar[int] = 120
    MAX_SECONDS: ClassVar[float] = (2**32 - 2) / 1000

    def __new__(cls, value: int | float = DEFAULT) -> Timeout:
        if isinstance(value, Timeout):
            return value
        message = f"Timeout must be finite positive numeric seconds, at most {cls.MAX_SECONDS}."
        if type(value) not in {int, float}:
            raise InvalidOption(message)
        try:
            seconds = float(value)
        except OverflowError as error:
            raise InvalidOption(message) from error
        if (
            not math.isfinite(seconds)
            or seconds <= 0
            or value > cls.MAX_SECONDS
            or seconds > cls.MAX_SECONDS
            or math.ceil(seconds * 1000) > 2**32 - 2
        ):
            raise InvalidOption(message)
        return float.__new__(cls, seconds)
