# SPDX-License-Identifier: AGPL-3.0-only
"""Decode a registered answer through the shared contract engine."""

from collections.abc import Mapping

from odfa11y.contracts import decode
from odfa11y.errors import PlanError


def decode_answer[T](answer_type: type[T], values: Mapping[str, object], label: str) -> T:
    return decode(answer_type, values, label=label, error=PlanError)
