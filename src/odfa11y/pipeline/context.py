# SPDX-License-Identifier: MPL-2.0
"""Internal run settings combine public values without duplicating tool selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from odfa11y.errors import PlanError
from odfa11y.tools import Tools

from .profiles import DEFAULT_PROFILE, Profile

if TYPE_CHECKING:
    from odfa11y.outcomes import ProgressObserver


@dataclass(frozen=True, slots=True)
class RunSettings:
    """The engine's tools, effective profile and optional observer."""

    tools: Tools = field(default_factory=Tools)
    profile: Profile = DEFAULT_PROFILE
    on_progress: ProgressObserver | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Require a profile value rather than a deferred string lookup.

        Raises
        ------
        PlanError
            The caller supplied a name instead of a Profile value.

        """
        if not isinstance(self.profile, Profile):
            message = "A run requires a Profile value."
            raise PlanError(message)
