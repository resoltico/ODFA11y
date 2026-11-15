# SPDX-License-Identifier: MPL-2.0
"""Internal run settings combine public values without duplicating tool selection."""

from dataclasses import dataclass, field

from odfa11y.application.tools import Tools
from odfa11y.errors import InvalidOption
from odfa11y.run.profiles import DEFAULT_PROFILE, Profile
lazy from odfa11y.progress import ProgressObserver


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
        InvalidOption
            The caller supplied a name instead of a Profile value.

        """
        if not isinstance(self.profile, Profile):
            message = "A run requires a Profile value."
            raise InvalidOption(message)
