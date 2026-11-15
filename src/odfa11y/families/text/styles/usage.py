# SPDX-License-Identifier: MPL-2.0
"""Text style usage measurements."""

from typing import TypedDict


class StyleUsage(TypedDict):
    """A style's usage count, parent and effective spacing in an adapter report."""

    style: str
    count: int
    parent: str | None
    spacing: dict[str, str]
